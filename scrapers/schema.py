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
            # Pre-clean: keep only digits, dots and commas
            v_clean = re.sub(r"[^\d.,]", "", v)
            
            # If there is both . and , determine which is decimal
            if "." in v_clean and "," in v_clean:
                if v_clean.rfind(",") > v_clean.rfind("."):
                    # PT Style: 10.500,00
                    v_clean = v_clean.replace(".", "").replace(",", ".")
                else:
                    # EN Style: 10,500.00
                    v_clean = v_clean.replace(",", "")
            # If only , we assume it is decimal in PT context
            elif "," in v_clean:
                # Unless it looks like a thousands separator (e.g. 10,000)
                # But in PT 10,000 is 10 with 3 decimal zeros.
                # Usually car prices don't have 3 decimal places.
                # If it's something like 15,000 it's likely 15000 in a car context.
                # Most PT sites use . for thousands.
                # Let's check if it's followed by 3 digits at the end.
                parts = v_clean.split(",")
                if len(parts) == 2 and len(parts[1]) == 3:
                    # Likely thousands
                    v_clean = v_clean.replace(",", "")
                else:
                    v_clean = v_clean.replace(",", ".")
            # If only .
            elif "." in v_clean:
                # If there are 3 digits after the dot, and no other dots, 
                # it's likely a thousands separator in PT (e.g., 10.500)
                parts = v_clean.split(".")
                if len(parts) == 2 and len(parts[1]) == 3:
                    v_clean = v_clean.replace(".", "")
                # If multiple dots, they are definitely thousands separators
                elif len(parts) > 2:
                    v_clean = v_clean.replace(".", "")
            
            # Final pass to ensure it's a valid float string
            v_clean = re.sub(r"[^\d.]", "", v_clean)
            try:
                return float(v_clean)
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
            # Try to find a 4-digit number that looks like a year
            match = re.search(r"\b(19|20)\d{2}\b", v)
            if match:
                return int(match.group(0))
            
            # Fallback to just digits if it's a short string
            v_digits = re.sub(r"[^\d]", "", v)
            if len(v_digits) == 4:
                try:
                    return int(v_digits)
                except ValueError:
                    return None
        return None
