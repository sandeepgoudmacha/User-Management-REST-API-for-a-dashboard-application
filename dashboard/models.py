"""Data models for the Brandmark API."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, validator
import re

if TYPE_CHECKING:
    pass


class ProviderType(str, Enum):
    """Provider type enumeration."""
    DOMAIN = "domain"
    SOCIAL = "social"
    APP_STORE = "app_store"
    PACKAGE_REGISTRY = "package_registry"
    DEV_PLATFORM = "dev_platform"


class CheckStatus(str, Enum):
    """Check status enumeration."""
    PENDING = "pending"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class ProviderResult(BaseModel):
    """Individual provider check result."""
    provider: str
    name: str
    available: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    checked_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class NameCheckSummary(BaseModel):
    """Summary of a name check across all providers."""
    total_checked: int = 0
    available: int = 0
    unavailable: int = 0
    pending: int = 0
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)


class NameCheck(BaseModel):
    """Complete name availability check result."""
    id: str
    name: str
    status: CheckStatus
    results: Dict[str, Dict[str, ProviderResult]] = {}
    summary: NameCheckSummary
    # brandability_analysis: Optional['BrandabilityAnalysisResponse'] = None
    created_at: datetime
    expires_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class BrandabilityMetrics(BaseModel):
    """Brandability scoring metrics."""
    pronounceability: float = Field(ge=0.0, le=1.0)
    memorability: float = Field(ge=0.0, le=1.0)
    length_score: float = Field(ge=0.0, le=1.0)
    uniqueness: float = Field(ge=0.0, le=1.0)


class Suggestion(BaseModel):
    """Name suggestion with availability and brandability data."""
    name: str
    score: float = Field(ge=0.0, le=1.0)
    generated_by: str  # "deterministic" | "llm"
    availability: Dict[str, Any] = {}
    brandability: BrandabilityMetrics
    metadata: Optional[Dict[str, Any]] = None


class SimilarNameSource(BaseModel):
    """Source where a similar name was found."""
    platform: str
    url: Optional[str] = None
    type: str  # "repository", "package", "domain", etc.
    title: Optional[str] = None


class SimilarName(BaseModel):
    """Similar name discovery result."""
    name: str
    similarity: float = Field(ge=0.0, le=1.0)
    found_in: List[str]
    sources: List[SimilarNameSource]


class SimilarNamesResponse(BaseModel):
    """Response for similar name discovery."""
    base_name: str
    similar_names: List[SimilarName]
    total_found: int
    search_time_ms: int


# Request Models

class NameCheckOptions(BaseModel):
    """Options for name checking."""
    domains: Optional[List[str]] = ["com", "io", "app"]
    deep_check: bool = False
    include_similar: bool = True
    include_ai_intelligence: bool = False


class NameCheckRequest(BaseModel):
    """Request for name availability checking."""
    name: str
    providers: List[str] = ["domains", "social"]
    options: NameCheckOptions = NameCheckOptions()

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v) < 2 or len(v) > 50:
            raise ValueError('Name must be 2-50 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Name contains invalid characters')
        return v.lower()

    @validator('providers')
    def validate_providers(cls, v):
        valid_providers = ['domains', 'social', 'app_stores', 'package_registries', 'dev_platforms']
        invalid = [p for p in v if p not in valid_providers]
        if invalid:
            raise ValueError(f'Invalid providers: {invalid}')
        return v


class SuggestionFilters(BaseModel):
    """Filters for name suggestions."""
    max_length: int = 15
    min_length: int = 4
    must_include: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    style: str = "modern"  # "modern", "professional", "creative", "technical"

    @validator('style')
    def validate_style(cls, v):
        valid_styles = ['modern', 'professional', 'creative', 'technical']
        if v not in valid_styles:
            raise ValueError(f'Style must be one of: {valid_styles}')
        return v


class SuggestionRequest(BaseModel):
    """Request for name suggestions."""
    keywords: List[str]
    count: int = Field(default=20, ge=1, le=100)
    filters: SuggestionFilters = SuggestionFilters()
    check_availability: bool = True
    target_providers: List[str] = ["domains", "npm", "social"]
    profile: str = Field(default="general", description="Search profile: general, startup, influencer, enterprise")

    @validator('keywords')
    def validate_keywords(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one keyword is required')
        return [keyword.lower().strip() for keyword in v if keyword.strip()]


class SuggestionResponse(BaseModel):
    """Response for name suggestions."""
    suggestions: List[Suggestion]
    total_generated: int
    filtered_count: int
    generation_time_ms: int


class DiscoverRequest(BaseModel):
    """Request for similar name discovery."""
    name: str
    sources: List[str] = ["web", "marketplaces", "registries"]
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    limit: int = Field(default=50, ge=1, le=200)
    profile: str = Field(default="general", description="Search profile: general, startup, influencer, enterprise")
    status_filter: str = Field(default=None, description="Filter by status: available, taken, unknown")
    category_filter: str = Field(default=None, description="Filter by category: domain, social, package")

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v) < 2 or len(v) > 50:
            raise ValueError('Name must be 2-50 characters')
        return v.lower().strip()


class BulkCheckRequest(BaseModel):
    """Request for bulk name checking."""
    names: List[str]
    providers: List[str] = ["domains", "npm", "github"]
    options: NameCheckOptions = NameCheckOptions()

    @validator('names')
    def validate_names(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one name is required')
        if len(v) > 50:
            raise ValueError('Maximum 50 names allowed per bulk request')
        
        validated = []
        for name in v:
            if not name or len(name) < 2 or len(name) > 50:
                raise ValueError(f'Name "{name}" must be 2-50 characters')
            if not re.match(r'^[a-zA-Z0-9_-]+$', name):
                raise ValueError(f'Name "{name}" contains invalid characters')
            validated.append(name.lower().strip())
        
        return validated


class BulkCheckResponse(BaseModel):
    """Response for bulk name checking."""
    batch_id: str
    status: str
    total_names: int
    results: List[NameCheck]
    estimated_completion: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ProviderStatus(BaseModel):
    """Status of an individual provider."""
    status: str  # "operational", "degraded", "unavailable"
    response_time_ms: int
    success_rate: float = Field(ge=0.0, le=1.0)
    rate_limit_remaining: Optional[int] = None


class ProvidersStatusResponse(BaseModel):
    """Response for provider status check."""
    providers: Dict[str, ProviderStatus]




class APIError(BaseModel):
    """Standard API error response."""
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    provider_errors: Optional[List[str]] = None
    timestamp: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Brandability Analysis Models

class BrandabilityDimensionResponse(BaseModel):
    """Individual brandability dimension response."""
    score: float = Field(ge=0.0, le=100.0)
    explanation: str
    examples: List[str]


class BrandabilityMarketContextResponse(BaseModel):
    """Market context analysis response."""
    similar_brands: List[str]
    positioning: str
    differentiation_score: float = Field(ge=0.0, le=100.0)


class BrandabilityAnalysisResponse(BaseModel):
    """Complete brandability analysis response."""
    name: str
    overall_score: float = Field(ge=0.0, le=100.0)
    dimensions: Dict[str, BrandabilityDimensionResponse]
    strengths: List[str]
    weaknesses: List[str]
    market_context: BrandabilityMarketContextResponse
    confusion_risks: List[str]
    recommendations: List[str]
    verdict: str  # "recommended", "reconsider", "avoid"
    verdict_reasoning: str
    analysis_timestamp: datetime
    industry: Optional[str] = None
    target_audience: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Brand DNA Matching Models

class BrandDNARequest(BaseModel):
    """Request for Brand DNA analysis."""
    name: str
    industry: Optional[str] = None
    use_ai_enhancement: bool = True
    use_cache: bool = True

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v) < 2 or len(v) > 50:
            raise ValueError('Name must be 2-50 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Name contains invalid characters')
        return v.strip()


class BrandDNAPatternResponse(BaseModel):
    """Individual DNA pattern response."""
    pattern_name: str
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    examples: List[str]


class BrandDNAMatchResponse(BaseModel):
    """DNA match against successful brand."""
    target_brand: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    matching_patterns: List[str]
    success_probability: float = Field(ge=0.0, le=1.0)
    valuation_prediction: Dict[str, float]
    confidence_level: str
    key_insights: List[str]


class BrandDNAAnalysisResponse(BaseModel):
    """Complete Brand DNA analysis response."""
    brand_name: str
    industry: str
    overall_dna_score: float = Field(ge=0.0, le=100.0)
    success_probability: float = Field(ge=0.0, le=1.0)

    # Pattern Analysis
    detected_patterns: List[BrandDNAPatternResponse]
    strongest_patterns: List[str]
    weakness_patterns: List[str]

    # Similarity Matching
    top_matches: List[BrandDNAMatchResponse]
    dna_archetype: str

    # Predictions
    valuation_trajectory: Dict[str, float]
    success_factors: List[str]
    risk_factors: List[str]

    # Advanced Insights
    competitive_dna_strength: float = Field(ge=0.0, le=1.0)
    acquisition_attractiveness: float = Field(ge=0.0, le=1.0)
    brand_evolution_potential: float = Field(ge=0.0, le=1.0)
    market_timing_score: float = Field(ge=0.0, le=1.0)

    # Metadata
    analysis_timestamp: datetime
    confidence_score: float = Field(ge=0.0, le=1.0)
    ai_provider_used: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Competitive Moat Analyzer Models

class CompetitiveMoatRequest(BaseModel):
    """Request for competitive moat analysis."""
    name: str
    industry: Optional[str] = None
    target_markets: Optional[List[str]] = None
    competitor_names: Optional[List[str]] = None
    use_ai_enhancement: bool = True

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v) < 2 or len(v) > 50:
            raise ValueError('Name must be 2-50 characters')
        return v.strip()


class TrademarkStrengthResponse(BaseModel):
    """Trademark strength analysis."""
    overall_strength: float = Field(ge=0.0, le=100.0)
    distinctiveness_score: float = Field(ge=0.0, le=100.0)
    enforceability_score: float = Field(ge=0.0, le=100.0)
    international_protection: float = Field(ge=0.0, le=100.0)
    risk_assessment: str
    strength_factors: List[str]
    vulnerability_factors: List[str]


class BrandDefensibilityResponse(BaseModel):
    """Brand defensibility scoring."""
    defensibility_score: float = Field(ge=0.0, le=100.0)
    trademark_strength: float = Field(ge=0.0, le=100.0)
    market_position_strength: float = Field(ge=0.0, le=100.0)
    competitive_barriers: List[str]
    vulnerability_points: List[str]
    defensive_recommendations: List[str]


class AcquisitionProbabilityResponse(BaseModel):
    """Acquisition probability analysis."""
    acquisition_probability: float = Field(ge=0.0, le=1.0)
    estimated_valuation_range: Dict[str, float]
    acquisition_triggers: List[str]
    strategic_value_factors: List[str]
    acquisition_timeline: str
    likely_acquirers: List[str]


class CompetitiveMoatAnalysisResponse(BaseModel):
    """Complete competitive moat analysis."""
    brand_name: str
    industry: str

    # Core Analysis
    trademark_strength: TrademarkStrengthResponse
    brand_defensibility: BrandDefensibilityResponse
    acquisition_probability: AcquisitionProbabilityResponse

    # Overall Metrics
    moat_strength_score: float = Field(ge=0.0, le=100.0)
    competitive_advantage: str
    moat_sustainability: float = Field(ge=0.0, le=1.0)

    # Strategic Insights
    competitive_threats: List[str]
    moat_building_opportunities: List[str]
    strategic_recommendations: List[str]

    # Metadata
    analysis_timestamp: datetime
    confidence_score: float = Field(ge=0.0, le=1.0)
    ai_provider_used: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

