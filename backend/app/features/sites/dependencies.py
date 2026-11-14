from typing import Annotated

from fastapi import Depends, Request

from app.features.sites.service import SiteService


def get_site_service(request: Request) -> SiteService:
    # Built once in app/main.py (the composition root) and stored on app.state.
    return request.app.state.site_service


SiteServiceDep = Annotated[SiteService, Depends(get_site_service)]
