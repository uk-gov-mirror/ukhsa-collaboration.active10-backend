from fastapi import APIRouter

router = APIRouter(prefix="/healthcheck", tags=["Healthcheck"])


@router.get("")
def healthcheck():
    pass
