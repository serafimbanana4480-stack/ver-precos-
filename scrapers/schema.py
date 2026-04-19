from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
import re

class VehicleListing(BaseModel):
    title: str
    price: Optional[float] = None
    url: Optional[str] = None
    year: Optional[int] = None
    km: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    location: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    source_id: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    horsepower: Optional[int] = None
    engine_size: Optional[int] = None
    doors: Optional[int] = None
    seats: Optional[int] = None
    color: Optional[str] = None
    seller_name: Optional[str] = None
    seller_type: Optional[str] = None
    extras: List[str] = Field(default_factory=list)

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Remove currency symbols and non-essential whitespace
            v = v.replace("€", "").replace("EUR", "").strip()
            
            # If there is both . and , we assume . is thousands and , is decimal
            if "." in v and "," in v:
                v = v.replace(".", "").replace(",", ".")
            # If only , we assume it is decimal
            elif "," in v:
                # But wait, if it's 10,000 it might be thousands (English style)
                # However, in PT it's decimal.
                # If there are exactly 3 digits after , it's ambiguous but usually thousands in English
                # and decimal in PT. Car prices in PT use , for decimal.
                v = v.replace(",", ".")
            # If only .
            elif "." in v:
                # If there are 3 digits after the dot, and no other dots, 
                # it's likely a thousands separator in PT (e.g., 10.500)
                parts = v.split(".")
                if len(parts) == 2 and len(parts[1]) == 3:
                    v = v.replace(".", "")
                # If multiple dots, they are definitely thousands separators
                elif len(parts) > 2:
                    v = v.replace(".", "")
            
            # Remove any remaining non-numeric characters except .
            v = re.sub(r"[^\d.]", "", v)
            try:
                return float(v)
            except ValueError:
                return None
        return None

    @field_validator("km", mode="before")
    @classmethod
    def parse_km(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            # Remove "km" and separators
            v = re.sub(r"[^\d]", "", v)
            try:
                return int(v)
            except ValueError:
                return None
        return None

    @field_validator("year", mode="before")
    @classmethod
    def parse_year(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            v = re.sub(r"[^\d]", "", v)
            try:
                return int(v)
            except ValueError:
                return None
        return None
