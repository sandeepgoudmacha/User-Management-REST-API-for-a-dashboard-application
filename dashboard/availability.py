"""Availability checking endpoints."""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.cache import get_cache_manager, get_rate_limiter
from app.models import (
    NameCheckRequest, NameCheck, NameCheckSummary, CheckStatus,
    BulkCheckRequest, BulkCheckResponse, ProviderResult
)
from app.providers import get_provider_manager
from app.services.brandability_analyzer import BrandabilityAnalyzer
from app.config import get_settings

router = APIRouter()


@router.post("/check", response_model=NameCheck)
async def check_name_availability(
    request: NameCheckRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    cache_manager = Depends(get_cache_manager),
    rate_limiter = Depends(get_rate_limiter)
):
    """Check name availability across specified providers."""
    
    # Generate check ID
    check_id = str(uuid.uuid4())
    
    # Create initial check record
    name_check = NameCheck(
        id=check_id,
        name=request.name,
        status=CheckStatus.PENDING,
        results={},
        summary=NameCheckSummary(),
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    
    # Get provider manager
    provider_manager = get_provider_manager()

    # Collect all provider checks to run in parallel
    check_tasks = []
    task_metadata = []  # Track provider_group and provider_name for each task

    for provider_group in request.providers:
        # Get providers in this group
        providers = provider_manager.get_providers_in_group(provider_group)

        for provider_name in providers:
            # Create async task for this provider check
            async def check_single_provider_wrapper(prov_name=provider_name, prov_group=provider_group):
                # Check rate limit
                if not await rate_limiter.check_rate_limit(prov_name):
                    return ProviderResult(
                        provider=prov_name,
                        name=request.name,
                        available=None,
                        confidence=0.0,
                        error="Rate limit exceeded",
                        checked_at=datetime.utcnow()
                    )

                # Check cache first
                cached_result = await cache_manager.get_availability(prov_name, request.name)
                if cached_result:
                    return cached_result

                # Perform actual check with timeout
                try:
                    result = await asyncio.wait_for(
                        provider_manager.check_availability(
                            prov_name,
                            request.name,
                            request.options.dict() if request.options else {}
                        ),
                        timeout=get_settings().provider_check_timeout
                    )
                    # Cache the result
                    await cache_manager.set_availability(prov_name, request.name, result)
                    return result
                except asyncio.TimeoutError:
                    return ProviderResult(
                        provider=prov_name,
                        name=request.name,
                        available=None,
                        confidence=0.0,
                        error="Request timeout",
                        checked_at=datetime.utcnow()
                    )
                except Exception as e:
                    return ProviderResult(
                        provider=prov_name,
                        name=request.name,
                        available=None,
                        confidence=0.0,
                        error=str(e),
                        checked_at=datetime.utcnow()
                    )

            check_tasks.append(check_single_provider_wrapper())
            task_metadata.append({
                'group': provider_group,
                'provider': provider_name
            })

    # Execute all checks in parallel with 10-second overall timeout
    try:
        results_list = await asyncio.wait_for(
            asyncio.gather(*check_tasks, return_exceptions=True),
            timeout=get_settings().total_request_timeout
        )
    except asyncio.TimeoutError:
        # If overall timeout exceeded, mark all as failed
        results_list = [Exception("Request timeout - check took longer than 10 seconds")] * len(check_tasks)

    # Organize results by provider group
    results = {}
    for metadata, result in zip(task_metadata, results_list):
        group = metadata['group']
        provider = metadata['provider']

        # Initialize group if needed
        if group not in results:
            results[group] = {}

        # Handle exceptions and errors
        if isinstance(result, Exception):
            result = ProviderResult(
                provider=provider,
                name=request.name,
                available=None,
                confidence=0.0,
                error=str(result),
                checked_at=datetime.utcnow()
            )

        results[group][provider] = result
    
    # Update name check with results
    name_check.results = results
    name_check.summary = calculate_summary(results)
    
    # If all results are cached, mark as complete
    all_complete = all(
        result.available is not None
        for group_results in results.values()
        for result in group_results.values()
    )
    
    if all_complete:
        name_check.status = CheckStatus.COMPLETE

    # === BRANDABILITY ANALYSIS (Conditional based on include_ai_intelligence) ===
    if request.options.include_ai_intelligence:
        try:
            from app.services.brandability_analyzer import BrandabilityAnalyzer
            from app.models import (
                BrandabilityAnalysisResponse, BrandabilityDimensionResponse,
                BrandabilityMarketContextResponse
            )

            brandability_analyzer = BrandabilityAnalyzer()
            await brandability_analyzer.initialize()

            brandability_result = await brandability_analyzer.analyze_brand(
                name=request.name,
                industry=None,  # Could be extracted from request options
                target_audience=None  # Could be extracted from request options
            )

            # Convert to response format
            dimensions_response = {}
            for dim_name, dim_data in brandability_result.dimensions.items():
                dimensions_response[dim_name] = BrandabilityDimensionResponse(
                    score=dim_data.score,
                    explanation=dim_data.explanation,
                    examples=dim_data.examples
                )

            market_context_response = BrandabilityMarketContextResponse(
                similar_brands=brandability_result.market_context.similar_brands,
                positioning=brandability_result.market_context.positioning,
                differentiation_score=brandability_result.market_context.differentiation_score
            )

            brandability_analysis_response = BrandabilityAnalysisResponse(
                name=brandability_result.name,
                overall_score=brandability_result.overall_score,
                dimensions=dimensions_response,
                strengths=brandability_result.strengths,
                weaknesses=brandability_result.weaknesses,
                market_context=market_context_response,
                confusion_risks=brandability_result.confusion_risks,
                recommendations=brandability_result.recommendations,
                verdict=brandability_result.verdict,
                verdict_reasoning=brandability_result.verdict_reasoning,
                analysis_timestamp=brandability_result.analysis_timestamp,
                industry=brandability_result.industry,
                target_audience=brandability_result.target_audience
            )

            # Add brandability analysis to the response
            name_check.brandability_analysis = brandability_analysis_response

        except Exception as e:
            print(f"⚠️ Brandability analysis failed: {e}")
            # Continue without brandability analysis if it fails
            pass


    return name_check


@router.get("/check/{provider}/{name}")
async def check_single_provider(
    provider: str,
    name: str,
    db: AsyncSession = Depends(get_db),
    cache_manager = Depends(get_cache_manager),
    rate_limiter = Depends(get_rate_limiter)
):
    """Check name availability for a single provider."""
    
    # Validate provider
    provider_manager = get_provider_manager()
    if not provider_manager.is_valid_provider(provider):
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    # Check rate limit
    if not await rate_limiter.check_rate_limit(provider):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Check cache first
    cached_result = await cache_manager.get_availability(provider, name)
    if cached_result:
        return cached_result.dict()
    
    # Check provider
    provider_manager = get_provider_manager()
    result = await provider_manager.check_availability(provider, name)
    
    # Cache result
    await cache_manager.set_availability(provider, name, result)
    
    return result.dict()


@router.post("/bulk/check", response_model=BulkCheckResponse)
async def bulk_check_availability(
    request: BulkCheckRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Check availability for multiple names."""
    
    batch_id = str(uuid.uuid4())
    results = []
    
    for name in request.names:
        # Create individual check request
        individual_request = NameCheckRequest(
            name=name,
            providers=request.providers,
            options=request.options
        )
        
        # Process check (this would be done asynchronously in production)
        check_result = await check_name_availability(
            individual_request,
            background_tasks,
            db
        )
        results.append(check_result)
    
    return BulkCheckResponse(
        batch_id=batch_id,
        status="processing",
        total_names=len(request.names),
        results=results,
        estimated_completion=datetime.utcnow() + timedelta(seconds=30)
    )


async def check_provider_availability(
    provider_name: str,
    name: str,
    check_id: str,
    options: Dict[str, Any],
    db: AsyncSession,
    cache_manager
):
    """Background task to check provider availability."""
    try:
        provider_manager = get_provider_manager()
        result = await provider_manager.check_availability(provider_name, name, options)
        
        # Cache the result
        await cache_manager.set_availability(provider_name, name, result)
        
        # Update database record would go here
        
    except Exception as e:
        # Log error and create error result
        error_result = ProviderResult(
            provider=provider_name,
            name=name,
            available=None,
            confidence=0.0,
            error=str(e),
            checked_at=datetime.utcnow()
        )
        
        await cache_manager.set_availability(provider_name, name, error_result)


def calculate_summary(results: Dict[str, Dict[str, ProviderResult]]) -> NameCheckSummary:
    """Calculate summary statistics for check results."""
    total_checked = 0
    available = 0
    unavailable = 0
    pending = 0
    
    for group_results in results.values():
        for result in group_results.values():
            total_checked += 1
            if result.available is None:
                pending += 1
            elif result.available:
                available += 1
            else:
                unavailable += 1
    
    # Calculate overall score (percentage of available names)
    overall_score = available / total_checked if total_checked > 0 else 0.0
    
    return NameCheckSummary(
        total_checked=total_checked,
        available=available,
        unavailable=unavailable,
        pending=pending,
        overall_score=overall_score
    )

