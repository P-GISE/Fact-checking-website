"""Bounded same-table excerpts; never infer semantic header or footnote scope."""
from factlens.source_document import SourceTrace,TableContext,TableContextFragment,fingerprint

CONTEXT_VERSION='table-context-v1'
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
    return TableContext(tableIndex=table_index,complete=complete,fragments=fragments)
