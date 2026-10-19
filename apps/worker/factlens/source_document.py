"""Bounded static-text parsing and observations, never source authentication."""
import hashlib
import ipaddress
from urllib.parse import urlsplit, urljoin, urlunsplit
from datetime import date, datetime
from email.message import Message
from typing import Literal
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, model_validator
from bs4.element import NavigableString, CData, Tag

PARSER_VERSION = 'static-text-v3'
MAX_BLOCKS = 2048
MAX_OBSERVATIONS = 32
MAX_NODES = 100000
MAX_DEPTH = 256


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TableLocation(Strict):
    # DOM order, not a resolved logical grid or authenticated semantic scope.
    tableIndex: int = Field(ge=0, lt=MAX_NODES)
    rowIndex: int | None = Field(default=None, ge=0, lt=MAX_NODES)
    cellIndex: int | None = Field(default=None, ge=0, lt=MAX_NODES)
    rowSpan: int | None = Field(default=None, ge=0, le=1000)
    columnSpan: int | None = Field(default=None, ge=1, le=1000)


class TextBlock(Strict):
    kind: Literal['title','heading','paragraph','table_header','table_cell','caption','note','text']
    position: int = Field(ge=0)
    length: int = Field(gt=0)
    tableLocation: TableLocation | None = None


class MetadataCandidate(Strict):
    value: str = Field(min_length=1, max_length=500)
    locator: str = Field(min_length=1, max_length=128)


class ObservedField(Strict):
    state: Literal['missing','observed','conflicting','invalid'] = 'missing'
    value: str | None = Field(default=None, max_length=500)
    candidates: list[MetadataCandidate] = Field(default_factory=list, max_length=MAX_OBSERVATIONS)


class Publication(Strict):
    publisher: ObservedField = Field(default_factory=ObservedField)
    publishedAt: ObservedField = Field(default_factory=ObservedField)
    modifiedAt: ObservedField = Field(default_factory=ObservedField)


def normalize_source_url(value: str, base_url: str | None = None) -> str:
    """Normalize a reference only; never resolve DNS or request its destination."""
    if not value or len(value)>2000 or any(c.isspace() or ord(c)<32 for c in value):
        raise ValueError('INVALID_SOURCE_URL')
    parsed=urlsplit(urljoin(base_url,value) if base_url else value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError('INVALID_SOURCE_URL')
    host=parsed.hostname.encode('idna').decode('ascii').lower().rstrip('.')
    port=parsed.port if parsed.port is not None else (443 if parsed.scheme=='https' else 80)
    if port not in (80,443) or not host or len(host)>253:
        raise ValueError('INVALID_SOURCE_URL')
    try:
        address=ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or host.endswith(('.localhost','.local','.internal')):
            raise ValueError('INVALID_SOURCE_URL')
        if any(not label or len(label)>63 or label.startswith('-') or label.endswith('-') or not all(c.isascii() and (c.isalnum() or c=='-') for c in label) for label in host.split('.')):
            raise ValueError('INVALID_SOURCE_URL')
    else:
        if address.version!=4 or not address.is_global:raise ValueError('INVALID_SOURCE_URL')
    netloc=host if port==(443 if parsed.scheme=='https' else 80) else f'{host}:{port}'
    result=urlunsplit((parsed.scheme,netloc,parsed.path or '/',parsed.query,''))
    if len(result)>2000:raise ValueError('INVALID_SOURCE_URL')
    return result


class SourceLink(Strict):
    kind: Literal['canonical','citation']
    url: str = Field(min_length=1,max_length=2000)
    locator: str = Field(min_length=1,max_length=128)


class TableContextFragment(Strict):
    blockIndex: int = Field(ge=0, lt=MAX_BLOCKS)
    kind: Literal['table_header','caption','note']
    text: str = Field(min_length=1, max_length=500)
    truncated: bool = False


class TableContext(Strict):
    version: Literal['table-context-v1'] = 'table-context-v1'
    tableIndex: int = Field(ge=0, lt=MAX_NODES)
    association: Literal['same_table_only'] = 'same_table_only'
    meaningVerified: Literal[False] = False
    complete: bool
    fragments: list[TableContextFragment] = Field(max_length=16)


class SourceTrace(Strict):
    parserVersion: Literal['static-text-v1','static-text-v2','static-text-v3'] = PARSER_VERSION
    requestedUrl: str
    finalUrl: str
    retrievedAt: str
    contentType: Literal['text/html','application/xhtml+xml','text/plain']
    bodySha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    textSha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    textLength: int = Field(ge=0)
    blocks: list[TextBlock] = Field(max_length=MAX_BLOCKS)
    structureComplete: bool
    publication: Publication
    quoteOccurrences: int | None = Field(default=None, ge=0)
    quoteBlockIndexes: list[int] = Field(default_factory=list, max_length=MAX_BLOCKS)
    extractionTruncated: bool = False
    sourceLinks: list[SourceLink] = Field(default_factory=list,max_length=32)
    sourceLinksComplete: bool = False
    tableContext: TableContext | None = None

    @model_validator(mode='after')
    def valid_locations(self):
        end = 0
        for block in self.blocks:
            if block.position < end or block.position + block.length > self.textLength:
                raise ValueError('INVALID_SOURCE_STRUCTURE')
            end = block.position + block.length
        if any(index < 0 or index >= len(self.blocks) for index in self.quoteBlockIndexes):
            raise ValueError('INVALID_QUOTE_BLOCK')
        if self.tableContext is not None:
            if (self.quoteOccurrences!=1 or not self.quoteBlockIndexes or any(
                    self.blocks[index].tableLocation is None or
                    self.blocks[index].tableLocation.tableIndex!=self.tableContext.tableIndex
                    for index in self.quoteBlockIndexes)):
                raise ValueError('INVALID_TABLE_CONTEXT')
            for fragment in self.tableContext.fragments:
                if fragment.blockIndex>=len(self.blocks):raise ValueError('INVALID_TABLE_CONTEXT')
                block=self.blocks[fragment.blockIndex]
                if block.kind!=fragment.kind or block.tableLocation is None or block.tableLocation.tableIndex!=self.tableContext.tableIndex:
                    raise ValueError('INVALID_TABLE_CONTEXT')
            if self.tableContext.complete and (not self.structureComplete or self.extractionTruncated or any(f.truncated for f in self.tableContext.fragments)):
                raise ValueError('INVALID_TABLE_CONTEXT')
        return self


def fingerprint(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def valid_date(value: str) -> bool:
    try:
        if len(value) == 10:
            return date.fromisoformat(value).isoformat() == value
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return 'T' in value and parsed.tzinfo is not None
    except ValueError:
        return False


def publication_observations(soup: BeautifulSoup) -> Publication:
    observations = {name: [] for name in ('publisher','publishedAt','modifiedAt')}
    invalid = set()
    names = {'publisher':'publisher','dc.publisher':'publisher','dcterms.publisher':'publisher',
             'article:published_time':'publishedAt','datepublished':'publishedAt','dcterms.issued':'publishedAt',
             'article:modified_time':'modifiedAt','datemodified':'modifiedAt','dcterms.modified':'modifiedAt'}
    # Attribute locations are server-generated ordinals, not model claims or selectors to execute.
    for index, tag in enumerate(soup.find_all(['meta','time'])):
        key = str(tag.get('property') or tag.get('name') or tag.get('itemprop') or '').lower()
        field = names.get(key)
        if field is None:
            continue
        value = ' '.join(str(tag.get('content') if tag.name == 'meta' else tag.get('datetime') or '').split())
        if not value or len(value) > 500 or len(observations[field]) >= MAX_OBSERVATIONS:
            invalid.add(field)
            continue
        observations[field].append(MetadataCandidate(value=value, locator=f'{tag.name}[{index}]@'+('content' if tag.name == 'meta' else 'datetime')))
        if field != 'publisher' and not valid_date(value):
            invalid.add(field)
    result = {}
    for field, candidates in observations.items():
        values = {candidate.value for candidate in candidates}
        state = 'invalid' if field in invalid else 'conflicting' if len(values) > 1 else 'observed' if values else 'missing'
        result[field] = ObservedField(state=state, value=next(iter(values)) if state == 'observed' else None, candidates=candidates)
    return Publication(**result)


def observed_span(node: Tag, attribute: str, minimum: int) -> int | None:
    value=node.get(attribute)
    if value is None:return 1
    if not isinstance(value,str) or not 1<=len(value)<=4 or not value.isascii() or not value.isdecimal():return None
    number=int(value)
    return number if minimum<=number<=1000 else None


def parse_document(body: bytes, content_type: str) -> dict:
    if not content_type.strip():
        raise ValueError('UNSUPPORTED_DOCUMENT')
    message = Message()
    message['content-type'] = content_type
    mime = message.get_content_type().lower()
    if mime not in ('text/html','application/xhtml+xml','text/plain'):
        raise ValueError('UNSUPPORTED_DOCUMENT')
    charset = message.get_content_charset() or 'utf-8'
    if charset.lower().replace('_','-') not in ('utf-8','utf8','us-ascii','ascii'):
        raise ValueError('UNSUPPORTED_ENCODING')
    try:
        decoded = body.decode(charset, errors='strict')
    except (UnicodeError, LookupError) as exc:
        raise ValueError('UNSUPPORTED_ENCODING') from exc
    if mime == 'text/plain':
        text = ' '.join(decoded.split())
        blocks = [TextBlock(kind='text', position=0, length=len(text))] if text else []
        return {'title':None,'text':text,'contentType':mime,'blocks':blocks,'structureComplete':True,'publication':Publication(),'sourceLinksRaw':[],'sourceLinksComplete':True,'hasBase':False}
    soup = BeautifulSoup(decoded, 'html.parser')
    title = soup.title.get_text(' ',strip=True) if soup.title else None
    for tag in soup(['script','style','noscript','template']):
        tag.decompose()
    chunks, blocks = [], []
    source_links, links_complete, has_base = [], True, False
    length, previous, complete = 0, None, True
    kinds = {'title':'title','h1':'heading','h2':'heading','h3':'heading','h4':'heading','h5':'heading','h6':'heading',
             'p':'paragraph','li':'paragraph','blockquote':'paragraph','th':'table_header','td':'table_cell',
             'caption':'caption','aside':'note','div':'text','pre':'text'}
    stack = [(iter(soup.children), None, None, None, None)]
    table_count = 0
    nodes = 0
    while stack:
        iterator, normal, special, table, row = stack[-1]
        node = next(iterator, None)
        if node is None:
            stack.pop()
            continue
        nodes += 1
        if nodes > MAX_NODES:
            raise ValueError('DOCUMENT_STRUCTURE_LIMIT')
        if isinstance(node, Tag):
            if node.name=='base':has_base=True
            rel=node.get('rel') or []
            rel=rel if isinstance(rel,list) else str(rel).lower().split()
            rel=[str(value).lower() for value in rel]
            kind='canonical' if node.name=='link' and 'canonical' in rel else 'citation' if (node.name in ('q','blockquote') and node.has_attr('cite')) or (node.name=='a' and 'cite' in rel) else None
            if kind is not None:
                attribute='cite' if node.name in ('q','blockquote') else 'href'
                value=node.get(attribute)
                if not isinstance(value,str) or not value or len(value)>2000 or len(source_links)>=32:
                    links_complete=False
                else:source_links.append({'kind':kind,'value':value,'locator':f'{node.name}[{nodes}]@{attribute}'})
            child_table, child_row = table, row
            if node.name=='table':
                child_table={'index':table_count,'nextRow':0}
                table_count+=1
                child_row=None
                normal=special=None
            elif node.name=='tr' and table is not None:
                child_row={'index':table['nextRow'],'nextCell':0}
                table['nextRow']+=1
            location=special[2] if special else None
            if node.name in ('th','td','caption'):
                location=None
                if table is not None:
                    caption=node.name=='caption'
                    location=TableLocation(tableIndex=table['index'],
                        rowIndex=row['index'] if row is not None and not caption else None,
                        cellIndex=row['nextCell'] if row is not None and not caption else None,
                        rowSpan=observed_span(node,'rowspan',0) if not caption else None,
                        columnSpan=observed_span(node,'colspan',1) if not caption else None)
                    if row is not None and not caption:row['nextCell']+=1
            child_normal = (id(node), kinds[node.name], None) if node.name in kinds else normal
            child_special = (id(node), kinds[node.name], location) if node.name in ('th','td','caption','aside') else special
            if len(stack) >= MAX_DEPTH:
                raise ValueError('DOCUMENT_STRUCTURE_LIMIT')
            stack.append((iter(node.children), child_normal, child_special, child_table, child_row))
            continue
        if type(node) not in (NavigableString, CData):
            continue
        value = ' '.join(str(node).split())
        if not value:
            continue
        identity, kind, location = special or normal or (id(node), 'text', None)
        position = length + (1 if chunks else 0)
        chunks.append(value)
        length = position + len(value)
        if previous == identity and blocks and complete:
            blocks[-1].length = length - blocks[-1].position
        elif len(blocks) < MAX_BLOCKS:
            blocks.append(TextBlock(kind=kind, position=position, length=len(value),tableLocation=location))
        else:
            complete = False
        previous = identity
    return {'title':title,'text':' '.join(chunks),'contentType':mime,'blocks':blocks,
            'structureComplete':complete,'publication':publication_observations(soup),
            'sourceLinksRaw':source_links,'sourceLinksComplete':links_complete,'hasBase':has_base}
