"""Trusted registry comparisons and possible dependencies; never fact authentication."""
from datetime import date
from pathlib import Path
from typing import Literal, Protocol
from collections.abc import Sequence
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from factlens.source_document import Strict, SourceTrace, normalize_source_url, fingerprint
class Reviewable(Protocol):
    url: str
    sourceTrace: SourceTrace | None
    reasons: list[str]

REVIEW_VERSION='source-review-v1'


class RegistryEntry(Strict):
    publisherId: str = Field(pattern=r'^[a-z0-9-]{1,64}$')
    name: str = Field(min_length=1,max_length=500)
    hosts: list[str] = Field(min_length=1,max_length=20)
    reviewedAt: date
    reviewReference: str = Field(min_length=1,max_length=2000)

    @model_validator(mode='after')
    def exact_hosts(self):
        if not self.name.strip() or not self.reviewReference.strip():raise ValueError('REGISTRY_REVIEW_REQUIRED')
        if len(self.hosts)!=len(set(self.hosts)):raise ValueError('DUPLICATE_REGISTRY_HOST')
        for host in self.hosts:
            normalized=normalize_source_url('https://'+host+'/')
            if urlsplit(normalized).hostname!=host:raise ValueError('INVALID_REGISTRY_HOST')
        return self


class SourceRegistry(Strict):
    version: str = Field(min_length=1,max_length=120)
    entries: list[RegistryEntry] = Field(max_length=100)

    @model_validator(mode='after')
    def distinct_entries(self):
        ids=[entry.publisherId for entry in self.entries]
        hosts=[host for entry in self.entries for host in entry.hosts]
        if len(ids)!=len(set(ids)) or len(hosts)!=len(set(hosts)):raise ValueError('AMBIGUOUS_SOURCE_REGISTRY')
        return self


class IdentityReview(Strict):
    status: Literal['unregistered','registered_origin','insecure_origin','publisher_conflict','publisher_unverified','trace_unavailable']
    publisherId: str | None = None
    registeredName: str | None = None


Signal=Literal['SAME_FINAL_URL','SAME_DOCUMENT_HASH','SAME_TEXT_HASH','DECLARED_SOURCE_LINK','SHARED_DECLARED_SOURCE','SAME_REGISTERED_PUBLISHER']


class SourceReview(Strict):
    version: Literal['source-review-v1'] = REVIEW_VERSION
    registryVersion: str
    identity: IdentityReview
    independence: Literal['unverified'] = 'unverified'
    groupId: str = Field(pattern=r'^[0-9a-f]{64}$')
    groupSize: int = Field(ge=1,le=5)
    relatedUrls: list[str] = Field(max_length=4)
    signals: list[Signal] = Field(max_length=6)


DEFAULT_REGISTRY=SourceRegistry.model_validate_json(Path(__file__).with_name('source_registry.json').read_text(encoding='utf-8'))


def normalized(value: str) -> str | None:
    try:return normalize_source_url(value)
    except (ValueError,UnicodeError):return None


def review_sources(checks: Sequence[Reviewable], registry: SourceRegistry | None = None) -> list[SourceReview]:
    if len(checks)>5:raise ValueError('SOURCE_REVIEW_LIMIT')
    registry=registry if registry is not None else DEFAULT_REGISTRY
    urls=[normalized(check.url) for check in checks]
    traces=[check.sourceTrace if check.sourceTrace and check.sourceTrace.finalUrl==check.url and 'SOURCE_TRACE_MISMATCH' not in check.reasons else None for check in checks]
    identities=[]
    for check,url,trace in zip(checks,urls,traces):
        if trace is None or url is None:
            identities.append(IdentityReview(status='trace_unavailable'));continue
        origin=urlsplit(url)
        entry=next((entry for entry in registry.entries if origin.hostname in entry.hosts),None)
        if entry is None:
            identities.append(IdentityReview(status='unregistered'));continue
        observed=trace.publication.publisher
        status='insecure_origin' if origin.scheme!='https' or origin.port not in (None,443) else 'publisher_unverified' if observed.state!='observed' else 'registered_origin' if observed.value==entry.name else 'publisher_conflict'
        identities.append(IdentityReview(status=status,publisherId=entry.publisherId,registeredName=entry.name))
    # Only possible dependency groups: no absence of an edge proves independence.
    parents=list(range(len(checks)))
    signals=[set() for _ in checks]
    def root(index: int) -> int:
        while parents[index]!=index:index=parents[index]
        return index
    for i in range(len(checks)):
        for j in range(i):
            a,b=traces[i],traces[j];found=set()
            if urls[i] is not None and urls[i]==urls[j]:found.add('SAME_FINAL_URL')
            if a and b:
                if a.textLength and b.textLength:
                    if a.bodySha256==b.bodySha256:found.add('SAME_DOCUMENT_HASH')
                    if a.textSha256==b.textSha256:found.add('SAME_TEXT_HASH')
                links_a={value for link in a.sourceLinks if (value:=normalized(link.url)) is not None}
                links_b={value for link in b.sourceLinks if (value:=normalized(link.url)) is not None}
                if (urls[j] is not None and urls[j] in links_a) or (urls[i] is not None and urls[i] in links_b):found.add('DECLARED_SOURCE_LINK')
                if links_a & links_b:found.add('SHARED_DECLARED_SOURCE')
            ia,ib=identities[i],identities[j]
            if ia.status==ib.status=='registered_origin' and ia.publisherId==ib.publisherId:found.add('SAME_REGISTERED_PUBLISHER')
            if found:
                parents[root(i)]=root(j);signals[i].update(found);signals[j].update(found)
    results=[]
    for i,identity in enumerate(identities):
        members=[j for j in range(len(checks)) if root(i)==root(j)]
        member_urls=sorted({urls[j] for j in members if urls[j] is not None})
        identifiers=sorted(urls[j] if urls[j] is not None else f'unresolved-candidate-{j}:'+fingerprint(checks[j].url.encode()) for j in members)
        group=fingerprint(('possible-dependency-v1\n'+'\n'.join(identifiers)).encode())
        results.append(SourceReview(registryVersion=registry.version,identity=identity,groupId=group,groupSize=len(members),
            relatedUrls=[url for url in member_urls if url!=urls[i]],signals=sorted(signals[i])))
    return results
