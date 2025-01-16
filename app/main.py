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
    is_valid: bool
    message: str
    safety_rating: Optional[str]
    location: Optional[dict]
    status: Optional[dict]

class ReferenceNumberRequest(BaseModel):
    reference_number: str

class ReferenceNumberDetails(BaseModel):
    reference_number: str
    origin: str
    destination: str
    equipment_type: str
    rate: str
    commodity: str

class ErrorResponse(BaseModel):
    detail: str


# Global dictionary to store loads
loads_dict = {}

def load_csv():
    """
    Load the CSV file into a DataFrame.
    """
    try:
        loads = {}
        with open("app/loads.csv", "r") as file:
            # Skip header
            headers = file.readline().strip().split(',')
            
            # Read data
            for line in file:
                values = line.strip().split(',')
                ref_num = values[0]  # reference_number is first column
                loads[ref_num] = {
                    "reference_number": values[0],
                    "origin": values[1],
                    "destination": values[2],
                    "equipment_type": values[3],
                    "rate": values[4],
                    "commodity": values[5]
                }
        return loads
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return {}

def get_loads():
    try:
        return pd.read_csv('loads.csv')
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return pd.DataFrame()

@app.on_event("startup")
def load_data():
    """
    Load the CSV into memory when the app starts.
    """
    global loads_dict
    loads_dict = load_csv()
    if not loads_dict:
        print("Warning: Load data is empty. Check 'loads.csv'")

@app.get(
    "/carriers/validate",
    response_model=CarrierValidation,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def validate_carrier(mc_number: str):
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
    mc_number = mc_number.upper().replace('MC', '').strip()
    
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
                    mc_number=mc_number,
                    is_valid=False,
                    message="Carrier not found",
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
                legal_name=carrier_data.get("legalName"),
                dba_name=carrier_data.get("dbaName"),
                is_valid=is_valid,
                safety_rating=carrier_data.get("safetyRating"),
                location = {
                        "state": carrier_data.get("phyState")
                    },
                status= {
                        "code": carrier_data.get("statusCode"),
                        "safety_rating_date": carrier_data.get("safetyRatingDate")
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


@app.get("/items/{reference_number}", response_model=ReferenceNumberDetails,
        responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    })
def read_item(reference_number: str):
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
    try:
        # Check if dictionary is empty
        if not loads_dict:
            raise HTTPException(
                status_code=500,
                detail="No load data available"
            )

        # Try to get the load
        load = loads_dict.get(reference_number)
        if not load:
            raise HTTPException(
                status_code=404,
                detail=f"Load not found: {reference_number}"
            )

        return ReferenceNumberDetails(
            reference_number=load["reference_number"],
            origin=load["origin"],
            destination=load["destination"],
            equipment_type=load["equipment_type"],
            rate=load["rate"],
            commodity=load["commodity"]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving load: {str(e)}"
        )

    