"""
CLI argument validation models using pydantic
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator, Field


class ScrapeArgs(BaseModel):
    """Validation model for scrape command arguments"""
    source: str = Field(default="all", description="Source to scrape")
    vehicle_type: str = Field(default="all", description="Vehicle type to scrape")
    max_listings: int = Field(default=50, gt=0, description="Maximum listings to scrape per source")
    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        valid_sources = ["olx", "standvirtual", "autosapo", "custojusto", "all"]
        if v not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}")
        return v
    
    @field_validator('vehicle_type')
    @classmethod
    def validate_vehicle_type(cls, v: str) -> str:
        valid_types = ["carros", "motos", "all"]
        if v not in valid_types:
            raise ValueError(f"vehicle_type must be one of {valid_types}")
        return v
    
    @classmethod
    def from_argparse(cls, args) -> 'ScrapeArgs':
        """Convert argparse Namespace to pydantic model"""
        return cls(
            source=args.source,
            vehicle_type=args.vehicle_type,
            max_listings=args.max_listings
        )


class TrainArgs(BaseModel):
    """Validation model for train command arguments"""
    force: bool = Field(default=False, description="Force retraining even if model exists")
    model_type: str = Field(default="xgboost", description="Model type to train")
    
    @field_validator('model_type')
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        valid_types = ["xgboost"]
        if v not in valid_types:
            raise ValueError(f"model_type must be one of {valid_types}")
        return v
    
    @classmethod
    def from_argparse(cls, args) -> 'TrainArgs':
        """Convert argparse Namespace to pydantic model"""
        return cls(
            force=args.force,
            model_type=getattr(args, 'model_type', 'xgboost')
        )


class FindDealsArgs(BaseModel):
    """Validation model for find-deals command arguments"""
    limit: int = Field(default=20, gt=0, description="Number of deals to find")
    min_profit: Optional[float] = Field(default=None, ge=0, description="Minimum profit potential")
    
    @classmethod
    def from_argparse(cls, args) -> 'FindDealsArgs':
        """Convert argparse Namespace to pydantic model"""
        return cls(
            limit=args.limit,
            min_profit=args.min_profit
        )


class ValuateArgs(BaseModel):
    """Validation model for valuate command arguments"""
    batch_size: int = Field(default=100, gt=0, description="Number of vehicles to process")
    
    @classmethod
    def from_argparse(cls, args) -> 'ValuateArgs':
        """Convert argparse Namespace to pydantic model"""
        return cls(
            batch_size=args.batch_size
        )


class DashboardArgs(BaseModel):
    """Validation model for dashboard command arguments"""
    port: int = Field(default=8501, ge=1, le=65535, description="Dashboard port")
    
    @classmethod
    def from_argparse(cls, args) -> 'DashboardArgs':
        """Convert argparse Namespace to pydantic model"""
        return cls(
            port=args.port
        )
