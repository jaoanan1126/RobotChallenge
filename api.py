from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import os

app = FastAPI()

class CarrierRequest(BaseModel):
    mc_number: str

class CarrierValidation(BaseModel):
    mc_number: str
    legal_name: Optional[str]
    dba_name: Optional[str]
    dot_number: Optional[str]
    operating_status: Optional[str]
    is_valid: bool
    insurance: dict
    authority_status: dict
    message: str

class ReferenceNumberRequest(BaseModel):
    reference_number: str

class ReerenceNumberDetails(BaseModel):
    reference_number: str
    origin: str
    destination: str
    equipment_type: str
    rate: str
    commodity: str

class ErrorResponse(BaseModel):
    detail: str
    
@app.post(
    "/carriers/validate",
    response_model=CarrierValidation,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def validate_carrier(carrier: CarrierRequest):
    """
    Validate carrier using FMCSA API
    
    Parameters:
    - mc_number: Motor Carrier number (can include 'MC' prefix)
    
    Returns:
    - Carrier validation details including operating status and insurance
    
    Raises:
    - 400: Invalid MC number or validation failed
    - 500: Server error or FMCSA API error
    """
    # Get API key from environment
    fmcsa_api_key = os.getenv("FMCSA_API_KEY")
    if not fmcsa_api_key:
        raise HTTPException(
            status_code=500,
            detail="FMCSA API key not configured"
        )

    # Clean MC number (remove 'MC' prefix if present)
    mc_number = carrier.mc_number.upper().replace('MC', '').strip()
    
    # Validate MC number format
    if not mc_number.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Invalid MC number format"
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://mobile.fmcsa.dot.gov/qc/services/carriers/{mc_number}",
                params={"webKey": fmcsa_api_key}
            )
            
            if response.status_code == 404:
                return CarrierValidation(
                    mc_number=carrier.mc_number,
                    is_valid=False,
                    message="Carrier not found",
                    insurance={},
                    authority_status={}
                )
                
            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"FMCSA API error: {response.text}"
                )

            # Parse FMCSA response
            data = response.json()
            carrier_data = data.get("content", {}).get("carrier", {})
            
            # Check if carrier is valid
            is_valid = carrier_data.get("allowedToOperate", "").upper() == "Y"
            
            # Create response
            return CarrierValidation(
                mc_number=f"MC{mc_number}",
                dot_number=carrier_data.get("dotNumber"),
                legal_name=carrier_data.get("legalName"),
                dba_name=carrier_data.get("dbaName"),
                is_valid=is_valid,
                safety_rating=carrier_data.get("safetyRating"),
                details={
                    "operation": {
                        "type": carrier_data.get("carrierOperation", {}).get("carrierOperationDesc"),
                        "code": carrier_data.get("carrierOperation", {}).get("carrierOperationCode")
                    },
                    "fleet_size": {
                        "drivers": carrier_data.get("totalDrivers"),
                        "power_units": carrier_data.get("totalPowerUnits")
                    },
                    "location": {
                        "state": carrier_data.get("phyState")
                    },
                    "status": {
                        "code": carrier_data.get("statusCode"),
                        "safety_rating": carrier_data.get("safetyRating"),
                        "safety_rating_date": carrier_data.get("safetyRatingDate")
                    }
                },
                message="Carrier is authorized to operate" if is_valid else "Carrier is not authorized to operate"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error validating carrier: {str(e)}"
        )


@app.get("/items/{reference_number}")
async def read_item(reference_number):
    """
    Validate reference number using csv
    
    Parameters:
    - reference_number: Unique identifier for each load (given by the caller)
    
    Returns:
    -  JSON-formatted load details matching the structure of the provided CSV.
    
    Raises:
    - 400: Invalid reference number or validation failed
    - 500: Server error
    """
    return {"item_id": reference_number}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)