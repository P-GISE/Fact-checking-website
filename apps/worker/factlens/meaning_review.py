from datetime import date
from decimal import Decimal
import json
import logging
from pathlib import Path
import re
from typing import Annotated, Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from factlens.source_document import SourceTrace, fingerprint, normalize_source_url

if TYPE_CHECKING:
    from factlens.contracts import Claim
    from factlens.validator import EvidenceDocument


logger = logging.getLogger(__name__)

Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


def https_url(value: str) -> str:
    normalized = normalize_source_url(value)
    if not normalized.startswith('https://') or normalized != value:
        raise ValueError('normalized HTTPS URL required')
    return value


def iso_date(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError('ISO date required')
    return value


class MeaningReview(Strict):
    version: Literal['reviewed-meaning-v1'] = 'reviewed-meaning-v1'
    verified: Literal[True] = True
    policyId: str = Field(min_length=1, max_length=120)
    sourceKind: Literal['paragraph', 'table']
    documentHash: Hash
    definition: str = Field(min_length=1, max_length=1000)
    quotePosition: int = Field(ge=0)
    quoteLength: int = Field(gt=0)
    relation: Literal['SUPPORTED', 'REFUTED']
    reviewReference: str
    reviewedAt: str

    _url = field_validator('reviewReference')(https_url)
    _date = field_validator('reviewedAt')(iso_date)

    @field_validator('verified', mode='before')
    @classmethod
    def true_boolean(cls, value: object) -> bool:
        if value is not True:
            raise ValueError('verified must be true')
        return value


class ReviewedContext(Strict):
    kind: Literal['text', 'paragraph']
    sha256: Hash
    title: str = Field(min_length=1, max_length=1000)


class ReviewedTable(Strict):
    tableIndex: int = Field(ge=0)
    rowHeaderBlockIndex: int = Field(ge=0)
    columnHeaderBlockIndex: int = Field(ge=0)
    valueBlockIndex: int = Field(ge=0)
    rowHeaderText: str | None = Field(default=None, min_length=1, max_length=1000)
    columnHeaderText: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode='after')
    def paired_headers(self) -> 'ReviewedTable':
        if (self.rowHeaderText is None) != (self.columnHeaderText is None):
            raise ValueError('both exact header texts required')
        return self


def record_valid(subject, period, metric, value, unit) -> bool:
    if subject not in ('한국', '대한민국') or unit != {'실업률': '%', '고용률': '%', '인구': '명'}.get(metric):
        return False
    if not re.fullmatch(r'(?:19|20)\d{2}년', period or '') or not re.fullmatch(r'(?:0|[1-9]\d*)(?:\.\d+)?', value or ''):
        return False
    number = Decimal(value)
    return number <= 100 if unit == '%' else number == number.to_integral_value()


def decimal_places(value: str) -> int:
    return len(value.partition('.')[2])


class ReviewedPolicy(Strict):
    policyId: str = Field(min_length=1, max_length=120)
    url: str
    documentHash: Hash | None
    sourceKind: Literal['paragraph', 'table']
    quote: str = Field(min_length=1)
    quotePosition: int = Field(ge=0)
    publisher: str = Field(min_length=1, max_length=500)
    publishedAt: str | None
    subject: str
    period: str
    metric: str
    value: str
    unit: str
    definition: str = Field(min_length=1, max_length=1000)
    precision: int = Field(ge=0, le=20)
    reviewReference: str
    reviewedAt: str
    context: ReviewedContext | None = None
    publicationDateText: str | None = None
    table: ReviewedTable | None = None
    publicationMode: Literal['published', 'live_dataset'] = 'published'
    originId: str | None = Field(default=None, max_length=120, pattern=r'^[a-z0-9][a-z0-9-]*$')

    _url = field_validator('url', 'reviewReference')(https_url)
    _date = field_validator('reviewedAt')(iso_date)

    @field_validator('publishedAt')
    @classmethod
    def optional_publication_date(cls, value: str | None) -> str | None:
        return iso_date(value) if value is not None else None

    @model_validator(mode='after')
    def consistent_scope(self) -> 'ReviewedPolicy':
        if (self.documentHash is None) == (self.context is None):
            raise ValueError('exactly one document or whole context hash required')
        if (self.sourceKind == 'table') != (self.table is not None) or (self.table and self.context):
            raise ValueError('table policy requires a full document and table anchors')
        if self.publicationMode == 'live_dataset':
            if (self.table is None or self.table.rowHeaderText is None
                    or self.publishedAt is not None or self.publicationDateText is not None):
                raise ValueError('undated live dataset requires exact reviewed table headers')
        elif self.publishedAt is None:
            raise ValueError('published source requires a publication date')
        if not record_valid(self.subject, self.period, self.metric, self.value, self.unit):
            raise ValueError('unsupported reviewed fact')
        if decimal_places(self.value) != self.precision or not self.definition.strip():
            raise ValueError('explicit definition and literal precision required')
        if self.publicationDateText is not None:
            dates = re.findall(r'\d{4}[-.]\d{2}[-.]\d{2}', self.publicationDateText)
            if len(dates) != 1 or dates[0].replace('.', '-') != self.publishedAt:
                raise ValueError('visible publication date must match reviewed date')
        return self


def load_policies(path: str | Path) -> list[ReviewedPolicy]:
    policies = TypeAdapter(list[ReviewedPolicy]).validate_python(json.loads(Path(path).read_text(encoding='utf-8')), strict=True)
    if len({policy.policyId for policy in policies}) != len(policies):
        raise ValueError('duplicate policy ID')
    return policies


DEFAULT_POLICIES = load_policies(Path(__file__).with_name('reviewed_sources.json'))


def claim_matches(claim: 'Claim') -> bool:
    if not record_valid(claim.subject, claim.period, claim.metric, claim.value, claim.unit):
        return False
    unit = r'(?:%|퍼센트)' if claim.unit == '%' else '명'
    pattern = (re.escape(claim.period) + r' ' + re.escape(claim.subject) + r'(?:의)? '
               + re.escape(claim.metric) + r'(?:은|는)? ' + re.escape(claim.value)
               + r' ?' + unit + r'(?:입니다)?\.?')
    return all(isinstance(text, str) and re.fullmatch(pattern, text.strip()) is not None
               for text in (claim.text, claim.contextText))


def matching_policies(claim: 'Claim') -> list[ReviewedPolicy]:
    if not claim_matches(claim):
        return []
    return [policy for policy in DEFAULT_POLICIES
            if all(getattr(claim, field) == getattr(policy, field) for field in ('subject', 'period', 'metric', 'unit'))
            and decimal_places(claim.value) == policy.precision]


def _scope_start(policy: ReviewedPolicy, text: str, trace: SourceTrace) -> int | None:
    if policy.context is None:
        return 0 if fingerprint(text.encode()) == policy.documentHash else None
    context = policy.context
    matches = [i for i, block in enumerate(trace.blocks)
               if block.kind == context.kind and block.tableLocation is None
               and fingerprint(text[block.position:block.position + block.length].encode()) == context.sha256]
    if len(matches) != 1 or matches[0] == 0:
        return None
    index = matches[0]
    block, previous = trace.blocks[index], trace.blocks[index - 1]
    if text[previous.position:previous.position + previous.length] != context.title:
        return None
    if policy.quotePosition + len(policy.quote) > block.length:
        return None
    return block.position


def _publication_matches(policy: ReviewedPolicy, document, trace: SourceTrace) -> bool:
    pub = trace.publication
    if any(field.state in ('invalid', 'conflicting') for field in (pub.publisher, pub.publishedAt, pub.modifiedAt)):
        return False
    if document.publisher not in (None, policy.publisher) or document.publishedAt not in (None, policy.publishedAt):
        return False
    fields = ((pub.publisher, policy.publisher), (pub.publishedAt, policy.publishedAt))
    if any(field.state == 'observed' and field.value != expected for field, expected in fields):
        return False
    if policy.publicationMode == 'live_dataset':
        return pub.publishedAt.state == 'missing'
    if all(field.state == 'observed' for field, _ in fields):
        return True
    return bool(policy.context and policy.publicationDateText
                and document.text.count(policy.publicationDateText) == 1)


def _simple_table(policy: ReviewedPolicy, document, trace: SourceTrace) -> bool:
    table = policy.table
    if table is None or trace.parserVersion != 'static-text-v3':
        return False
    audit = trace.tableReferenceAudit
    if audit is None or not audit.complete or any(ref.status != 'resolved_same_table_header' for ref in audit.references):
        return False
    indexes = (table.rowHeaderBlockIndex, table.columnHeaderBlockIndex, table.valueBlockIndex)
    if len(set(indexes)) != 3 or any(index >= len(trace.blocks) for index in indexes):
        return False
    row, column, cell = [trace.blocks[index] for index in indexes]
    if row.kind != 'table_header' or column.kind != 'table_header' or cell.kind != 'table_cell':
        return False
    locations = [block.tableLocation for block in (row, column, cell)]
    if any(loc is None or loc.tableIndex != table.tableIndex for loc in locations):
        return False
    r, c, v = locations
    if any(loc.rowIndex is None or loc.cellIndex is None for loc in locations):
        return False
    if not (r.rowIndex == v.rowIndex and r.cellIndex < v.cellIndex
            and c.cellIndex == v.cellIndex and c.rowIndex < v.rowIndex):
        return False
    cells = [block for block in trace.blocks if block.tableLocation
             and block.tableLocation.tableIndex == table.tableIndex
             and block.kind in ('table_cell', 'table_header')]
    coordinates = set()
    for block in cells:
        loc = block.tableLocation
        if loc.rowSpan != 1 or loc.columnSpan != 1 or loc.rowIndex is None or loc.cellIndex is None:
            return False
        coordinate = (loc.rowIndex, loc.cellIndex)
        if coordinate in coordinates:
            return False
        coordinates.add(coordinate)
    if (table.rowHeaderText is None
            and len(coordinates) != (max(x[0] for x in coordinates) + 1) * (max(x[1] for x in coordinates) + 1)):
        return False
    row_text = document.text[row.position:row.position + row.length]
    column_text = document.text[column.position:column.position + column.length]
    if table.rowHeaderText is not None:
        headers_match = (row_text == table.rowHeaderText and column_text == table.columnHeaderText
                         and policy.metric in row_text and policy.unit in row_text
                         and column_text == policy.period.removesuffix('년'))
    else:
        headers_match = (policy.subject in row_text and policy.period in row_text
                         and policy.metric in column_text and policy.unit in column_text)
    return (headers_match and cell.position == document.position and cell.length == len(document.quote)
            and document.quote in (policy.value, policy.value + policy.unit))


def review_meaning(claim: 'Claim', document: 'EvidenceDocument') -> MeaningReview | None:
    candidates = matching_policies(claim)
    if not candidates or document.sourceTrace is None:
        return None
    try:
        trace = SourceTrace.model_validate(document.sourceTrace.model_dump())
        urls = (document.url, trace.requestedUrl, trace.finalUrl)
        if any(https_url(url) != document.url for url in urls):
            return None
    except ValueError:
        logger.info('REVIEWED_SOURCE_TRACE_REJECTED')
        return None
    if (trace.textSha256 != fingerprint(document.text.encode()) or trace.textLength != len(document.text)
            or not trace.structureComplete or trace.extractionTruncated):
        return None
    quote = document.quote
    if (not quote or document.position < 0
            or document.text[document.position:document.position + len(quote)] != quote):
        return None
    occurrences = sum(1 for _ in re.finditer('(?=' + re.escape(quote) + ')', document.text))
    matches = []
    for policy in candidates:
        if policy.url != document.url or policy.quote != quote:
            continue
        if policy.sourceKind != 'table' and occurrences != 1:
            continue
        if not re.search(r'(?<![\d.])' + re.escape(policy.value) + r'(?![\d.])', quote):
            continue
        if any(getattr(document.fact, field) != getattr(policy, field)
               for field in ('subject', 'period', 'metric', 'value', 'unit')):
            continue
        start = _scope_start(policy, document.text, trace)
        if start is None or start + policy.quotePosition != document.position or not _publication_matches(policy, document, trace):
            continue
        containing = [block for block in trace.blocks if block.position <= document.position
                      and block.position + block.length >= document.position + len(quote)]
        if len(containing) != 1:
            continue
        if policy.sourceKind == 'table':
            if not _simple_table(policy, document, trace):
                continue
        elif containing[0].kind not in ('paragraph', 'text') or containing[0].tableLocation is not None:
            continue
        matches.append(MeaningReview(
            policyId=policy.policyId, sourceKind=policy.sourceKind, documentHash=trace.textSha256,
            definition=policy.definition, quotePosition=document.position, quoteLength=len(quote),
            relation='SUPPORTED' if Decimal(claim.value) == Decimal(policy.value) else 'REFUTED',
            reviewReference=policy.reviewReference, reviewedAt=policy.reviewedAt))
    return matches[0] if len(matches) == 1 else None
