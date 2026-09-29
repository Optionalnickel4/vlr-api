"""Typed, closed request vocabulary for the private Jarvis query endpoint."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilitiesParams(_Params):
    pass


class MatchesListParams(_Params):
    state: Literal["live", "upcoming", "completed"]
    limit: int = Field(default=10, ge=1, le=25)
    team: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=64)
    ] | None = None
    event: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=128)
    ] | None = None


class MatchesGetParams(_Params):
    match_id: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,16}$")]


class TeamsSearchParams(_Params):
    query: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=64)
    ]
    limit: int = Field(default=8, ge=1, le=12)


class TeamsGetParams(_Params):
    team_id: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,16}$")]


class CapabilitiesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["capabilities"]
    params: CapabilitiesParams = Field(default_factory=CapabilitiesParams)


class MatchesListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["matches.list"]
    params: MatchesListParams


class MatchesGetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["matches.get"]
    params: MatchesGetParams


class TeamsSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["teams.search"]
    params: TeamsSearchParams


class TeamsGetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["teams.get"]
    params: TeamsGetParams


JarvisRequest = Annotated[
    CapabilitiesRequest | MatchesListRequest | MatchesGetRequest |
    TeamsSearchRequest | TeamsGetRequest,
    Field(discriminator="operation"),
]

JARVIS_REQUEST_ADAPTER = TypeAdapter(JarvisRequest)
