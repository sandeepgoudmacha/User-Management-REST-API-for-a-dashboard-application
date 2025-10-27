"""Batch operations router for checking multiple names."""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field, validator
import asyncio
from datetime import datetime
import uuid

from app.services.availability_checker import AvailabilityChecker
from app.cache import get_cache_manager, CacheManager
from app.models import CheckStatus, ProviderResult

router = APIRouter()


class BatchCheckRequest(BaseModel):
    """Request for batch name checking."""
    names: List[str] = Field(..., min_items=1, max_items=20, description="List of names to check")
    providers: List[str] = Field(default=["domains", "social"], description="Provider categories to check")
    parallel: bool = Field(default=True, description="Run checks in parallel")

    @validator('names')
    def validate_names(cls, v):
        # Remove duplicates and clean names
        cleaned = []
        seen = set()
        for name in v:
            clean_name = name.lower().strip()
            if clean_name and clean_name not in seen:
                cleaned.append(clean_name)
                seen.add(clean_name)
        if not cleaned:
            raise ValueError('At least one valid name is required')
        return cleaned


class BatchCheckResult(BaseModel):
    """Result for a single name in batch check."""
    name: str
    status: CheckStatus
    available_count: int
    total_count: int
    availability_percentage: float
    top_available: List[str]
    top_taken: List[str]
    check_id: str


class BatchCheckResponse(BaseModel):
    """Response for batch check operation."""
    batch_id: str
    total_names: int
    results: List[BatchCheckResult]
    summary: Dict[str, Any]
    processing_time_ms: int
    timestamp: datetime


class BatchComparisonRequest(BaseModel):
    """Request for comparing multiple names."""
    names: List[str] = Field(..., min_items=2, max_items=10)
    providers: List[str] = Field(default=["domains", "social"])
    criteria: List[str] = Field(default=["availability", "brandability", "memorability"])


class ComparisonResult(BaseModel):
    """Comparison result for names."""
    winner: str
    scores: Dict[str, float]
    detailed_comparison: Dict[str, Dict[str, Any]]
    recommendations: List[str]


@router.post("/check", response_model=BatchCheckResponse)
async def batch_check_names(
    request: BatchCheckRequest,
    background_tasks: BackgroundTasks,
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """
    Check availability for multiple names at once.

    Features:
    - Check up to 20 names simultaneously
    - Parallel processing for faster results
    - Cached results for efficiency
    - Summary statistics across all names
    """
    batch_id = str(uuid.uuid4())
    start_time = datetime.utcnow()

    # Initialize checker
    checker = AvailabilityChecker()

    async def check_single_name(name: str) -> BatchCheckResult:
        """Check a single name and return summary."""
        try:
            # Check cache first
            cache_key = f"batch_check:{name}:{'-'.join(sorted(request.providers))}"
            cached = await cache_manager.get(cache_key)
            if cached:
                return BatchCheckResult(**cached)

            # Perform check
            result = await checker.check_name(name, request.providers)

            # Calculate summary stats
            available_count = 0
            total_count = 0
            top_available = []
            top_taken = []

            for category, providers in result.results.items():
                for provider_name, provider_result in providers.items():
                    total_count += 1
                    if provider_result.available:
                        available_count += 1
                        top_available.append(f"{provider_name}")
                    elif provider_result.available is False:
                        top_taken.append(f"{provider_name}")

            availability_percentage = (available_count / total_count * 100) if total_count > 0 else 0

            batch_result = BatchCheckResult(
                name=name,
                status=result.status,
                available_count=available_count,
                total_count=total_count,
                availability_percentage=round(availability_percentage, 1),
                top_available=top_available[:5],  # Top 5 available
                top_taken=top_taken[:5],  # Top 5 taken
                check_id=result.id
            )

            # Cache result
            await cache_manager.set(cache_key, batch_result.dict(), ttl=300)

            return batch_result

        except Exception as e:
            # Return error result
            return BatchCheckResult(
                name=name,
                status=CheckStatus.ERROR,
                available_count=0,
                total_count=0,
                availability_percentage=0,
                top_available=[],
                top_taken=[],
                check_id=""
            )

    # Process names
    if request.parallel:
        # Parallel processing
        tasks = [check_single_name(name) for name in request.names]
        results = await asyncio.gather(*tasks)
    else:
        # Sequential processing
        results = []
        for name in request.names:
            result = await check_single_name(name)
            results.append(result)

    # Calculate batch summary
    total_available = sum(r.available_count for r in results)
    total_checked = sum(r.total_count for r in results)
    avg_availability = sum(r.availability_percentage for r in results) / len(results) if results else 0

    # Find best and worst availability
    best_name = max(results, key=lambda x: x.availability_percentage) if results else None
    worst_name = min(results, key=lambda x: x.availability_percentage) if results else None

    summary = {
        "total_names_checked": len(results),
        "total_platforms_checked": total_checked,
        "total_available": total_available,
        "average_availability": round(avg_availability, 1),
        "best_availability": {
            "name": best_name.name if best_name else None,
            "percentage": best_name.availability_percentage if best_name else 0
        },
        "worst_availability": {
            "name": worst_name.name if worst_name else None,
            "percentage": worst_name.availability_percentage if worst_name else 0
        }
    }

    # Calculate processing time
    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    return BatchCheckResponse(
        batch_id=batch_id,
        total_names=len(request.names),
        results=results,
        summary=summary,
        processing_time_ms=processing_time,
        timestamp=datetime.utcnow()
    )


@router.post("/compare", response_model=ComparisonResult)
async def compare_names(
    request: BatchComparisonRequest,
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """
    Compare multiple names and determine the best option.

    Compares names based on:
    - Overall availability across platforms
    - Brandability scores
    - Domain availability in key TLDs
    - Social media availability
    """
    # Check all names
    batch_request = BatchCheckRequest(
        names=request.names,
        providers=request.providers,
        parallel=True
    )

    batch_result = await batch_check_names(batch_request, BackgroundTasks(), cache_manager)

    # Score each name
    scores = {}
    detailed_comparison = {}

    for result in batch_result.results:
        # Calculate weighted score
        availability_score = result.availability_percentage / 100

        # Bonus for critical platforms
        critical_bonus = 0
        if any('.com' in p for p in result.top_available):
            critical_bonus += 0.1
        if any('instagram' in p.lower() for p in result.top_available):
            critical_bonus += 0.05
        if any('twitter' in p.lower() for p in result.top_available):
            critical_bonus += 0.05

        # Name quality score (simple heuristics)
        length_score = 1.0 - (abs(len(result.name) - 7) * 0.05)  # Optimal around 7 chars
        length_score = max(0, min(1, length_score))

        # Final score
        final_score = (
            availability_score * 0.6 +  # 60% weight on availability
            critical_bonus * 0.25 +      # 25% weight on critical platforms
            length_score * 0.15          # 15% weight on name quality
        )

        scores[result.name] = round(final_score * 100, 1)

        detailed_comparison[result.name] = {
            "availability": result.availability_percentage,
            "available_count": result.available_count,
            "total_count": result.total_count,
            "critical_platforms": {
                ".com": ".com" in ' '.join(result.top_available),
                "instagram": any("instagram" in p.lower() for p in result.top_available),
                "twitter": any("twitter" in p.lower() for p in result.top_available)
            },
            "top_available": result.top_available,
            "top_taken": result.top_taken
        }

    # Determine winner
    winner = max(scores, key=scores.get) if scores else None

    # Generate recommendations
    recommendations = []
    if winner:
        recommendations.append(f"'{winner}' has the best overall availability and brand potential")

        winner_details = detailed_comparison[winner]
        if winner_details["critical_platforms"][".com"]:
            recommendations.append(f"✅ {winner}.com is available - secure it immediately!")
        else:
            recommendations.append(f"⚠️ {winner}.com is taken - consider alternatives or negotiate purchase")

        if winner_details["availability"] < 70:
            recommendations.append("Consider variations of the name for better availability")

        # Suggest runners-up
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) > 1:
            runner_up = sorted_scores[1][0]
            recommendations.append(f"'{runner_up}' is a strong alternative with {sorted_scores[1][1]}% score")

    return ComparisonResult(
        winner=winner or "",
        scores=scores,
        detailed_comparison=detailed_comparison,
        recommendations=recommendations
    )


@router.post("/suggest-variations")
async def suggest_variations(name: str, count: int = 10):
    """
    Generate variations of a name for better availability.

    Techniques:
    - Add/remove prefixes and suffixes
    - Use synonyms and related words
    - Try different TLDs
    - Abbreviations and acronyms
    """
    variations = []

    # Common prefixes
    prefixes = ["get", "try", "use", "my", "the", "go", "be"]
    for prefix in prefixes[:3]:
        variations.append(f"{prefix}{name}")

    # Common suffixes
    suffixes = ["app", "hub", "lab", "pro", "io", "ly", "ify", "box", "zone"]
    for suffix in suffixes[:4]:
        variations.append(f"{name}{suffix}")

    # Truncations
    if len(name) > 5:
        variations.append(name[:-1])  # Remove last character
        variations.append(name[:-2])  # Remove last 2 characters

    # Doubling
    if len(name) <= 8:
        variations.append(f"{name}{name}")

    # Remove duplicates and limit
    variations = list(set(variations))[:count]

    return {
        "original": name,
        "variations": variations,
        "count": len(variations),
        "tip": "Check each variation's availability to find the best option"
    }