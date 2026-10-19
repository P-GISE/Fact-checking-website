"""Explicit HTML ID references only; structural resolution never proves meaning."""
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal

REFERENCE_VERSION='table-reference-audit-v1'
MAX_REFERENCES=32
MAX_IDS=2048

class HeaderReference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    cellBlockIndex:int=Field(ge=0,lt=2048)
    declaredId:str=Field(min_length=1,max_length=64)
    status:Literal['resolved_same_table_header','missing_id','duplicate_id','cross_table','not_header','unresolved']
    headerBlockIndex:int|None=Field(default=None,ge=0,lt=2048)

class TableReferenceAudit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:Literal['table-reference-audit-v1']=REFERENCE_VERSION
    meaningVerified:Literal[False]=False
    complete:bool
    references:list[HeaderReference]=Field(max_length=MAX_REFERENCES)


def index_ids(soup):
    counts={};complete=True
    # Count even excluded script/style IDs: duplicates remain ambiguous.
    for number,node in enumerate(soup.descendants):
        if number>=100000:raise ValueError('DOCUMENT_STRUCTURE_LIMIT')
        if not getattr(node,'attrs',None) or 'id' not in node.attrs:continue
        value=node.get('id')
        if not isinstance(value,str) or not 1<=len(value)<=64 or any(c.isspace() or ord(c)<32 for c in value):
            complete=False;continue
        if value in counts:counts[value]+=1
        elif len(counts)<MAX_IDS:counts[value]=1
        else:complete=False
    return counts,complete


def observe_references(cells,identities,blocks,id_counts,index_complete,structure_complete):
    indexes={}
    for index,identity in enumerate(identities):indexes.setdefault(identity,[]).append(index)
    targets={}
    for cell in cells:
        if cell['id'] is not None:targets.setdefault(cell['id'],[]).append(cell)
    output=[];complete=index_complete and structure_complete
    for cell in cells:
        if cell['headers'] is None:continue
        tokens=cell['headers']
        if not isinstance(tokens,list) or not tokens or len(tokens)>8:complete=False
        if not isinstance(tokens,list):continue
        positions=indexes.get(cell['identity'],[])
        if len(positions)!=1:complete=False;continue
        source=positions[0]
        for token in tokens[:8]:
            if len(output)>=MAX_REFERENCES:complete=False;break
            if not isinstance(token,str) or not 1<=len(token)<=64 or any(c.isspace() or ord(c)<32 for c in token):complete=False;continue
            target=None;status='unresolved'
            matches=targets.get(token,[])
            if index_complete:
                if id_counts.get(token,0)>1:status='duplicate_id'
                elif id_counts.get(token,0)==0:status='missing_id'
                elif not matches or matches[0]['kind']!='table_header':status='not_header'
                elif matches[0]['tableIndex']!=cell['tableIndex']:status='cross_table'
                else:
                    header_indexes=indexes.get(matches[0]['identity'],[])
                    if len(header_indexes)==1 and blocks[header_indexes[0]].kind=='table_header':
                        target=header_indexes[0];status='resolved_same_table_header'
                    else:complete=False
            output.append(HeaderReference(cellBlockIndex=source,declaredId=token,status=status,headerBlockIndex=target))
    return TableReferenceAudit(complete=complete,references=output)
