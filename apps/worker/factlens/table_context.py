"""Bounded same-table excerpts; never infer semantic header or footnote scope."""
import re
from factlens.source_document import SourceTrace,TableContext,TableContextFragment,TableCue,TableCueAudit,fingerprint

CONTEXT_VERSION='table-context-v1'
CUE_VERSION='table-cue-audit-v1'
CUE_PATTERNS={
 'period':re.compile(r'(?:19|20)\d{2}년|분기|연간|월간|전년\s*대비'),
 'denominator':re.compile(r'분모|\d{1,3}세\s*이상|전체\s*인구|가구\s*기준'),
 'correction':re.compile(r'정정|수정'),
 'unit':re.compile(r'퍼센트포인트|%p|%|백만\s*명|천\s*명|단위',re.I),
}
MAX_CONTEXT_FRAGMENTS=16
MAX_CONTEXT_TEXT=500


def build_table_context(text:str,trace:SourceTrace,position:int,quote:str)->TableContext|None:
    if (not quote or position<0 or text[position:position+len(quote)]!=quote
            or trace.quoteOccurrences!=1 or trace.textLength!=len(text)
            or trace.textSha256!=fingerprint(text.encode())):
        return None
    locations=[trace.blocks[index].tableLocation for index in trace.quoteBlockIndexes]
    if not locations or any(location is None for location in locations):return None
    tables={location.tableIndex for location in locations if location is not None}
    if len(tables)!=1:return None
    table_index=next(iter(tables))
    fragments=[]
    complete=trace.structureComplete and not trace.extractionTruncated
    for index,block in enumerate(trace.blocks):
        if (block.tableLocation is None or block.tableLocation.tableIndex!=table_index
                or block.kind not in ('table_header','caption','note')):continue
        if len(fragments)>=MAX_CONTEXT_FRAGMENTS:
            complete=False
            break
        original=text[block.position:block.position+block.length]
        truncated=len(original)>MAX_CONTEXT_TEXT
        complete=complete and not truncated
        fragments.append(TableContextFragment(blockIndex=index,kind=block.kind,
            text=original[:MAX_CONTEXT_TEXT],truncated=truncated))
    cues=[];cue_complete=complete
    for fragment in fragments:
        for kind,pattern in CUE_PATTERNS.items():
            match=pattern.search(fragment.text)
            if match is None:continue
            if len(cues)>=32:cue_complete=False;continue
            cues.append(TableCue(blockIndex=fragment.blockIndex,kind=kind,offset=match.start(),text=match.group()))
    return TableContext(tableIndex=table_index,complete=complete,fragments=fragments,
        cueAudit=TableCueAudit(complete=cue_complete,cues=cues))
