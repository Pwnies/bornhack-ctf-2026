import json, re, sys

# ---- Faithful HRM simulator matching sixlettervariables/hrmsandbox engine semantics ----
def parse(src):
    stmts=[]; labels={}
    for raw in src.splitlines():
        line=raw.split('--',1)[0].strip()
        if not line: continue
        if line.endswith(':'):
            name=line[:-1].strip()
            labels[name]=len(stmts)
            stmts.append(('label',name)); continue
        parts=line.split()
        op=parts[0].lower()
        arg=parts[1] if len(parts)>1 else None
        stmts.append((op,arg))
    return stmts,labels

def operand(arg):
    # returns ('direct', addr) or ('indirect', ptr_addr)
    m=re.fullmatch(r'\[(\d+)\]',arg)
    if m: return ('indirect', m.group(1))
    return ('direct', arg)

def load(vars, arg):
    kind,a=operand(arg)
    if kind=='direct':
        if a not in vars: raise RuntimeError(f"undefined var {a}")
        return vars[a]
    addr=vars[a]
    return vars[str(addr)]

def store(vars, arg, val):
    kind,a=operand(arg)
    if kind=='direct': vars[a]=val
    else: vars[str(vars[a])]=val

def checkval(v):
    if isinstance(v,str): return len(v)==1
    return -999<=v<=999

def run(src, inbox, variables, maxit=100000):
    stmts,labels=parse(src)
    vars={str(k):v for k,v in variables.items()}
    inbox=list(inbox); outbox=[]; hand=None; ip=0; it=0
    while 0<=ip<len(stmts) and it<maxit:
        it+=1
        op,arg=stmts[ip]; ip+=1
        if op in ('label','comment','define'): continue
        elif op=='inbox':
            if inbox: hand=inbox.pop(0)
            else: ip=-1
        elif op=='outbox':
            if hand is None: raise RuntimeError("empty hand outbox")
            outbox.append(hand)
        elif op=='copyfrom': hand=load(vars,arg)
        elif op=='copyto': store(vars,arg,hand)
        elif op in ('add','sub','bumpup','bumpdn'):
            if op=='bumpup':
                v=load(vars,arg)+1; store(vars,arg,v); hand=v
            elif op=='bumpdn':
                v=load(vars,arg)-1; store(vars,arg,v); hand=v
            elif op=='add': hand=hand+load(vars,arg)
            else: hand=hand-load(vars,arg)
            if not checkval(hand): raise RuntimeError("out of bounds")
        elif op=='jump': ip=labels[arg]
        elif op=='jumpz': ip=labels[arg] if hand==0 else ip
        elif op=='jumpn': ip=labels[arg] if hand<0 else ip
        else: raise RuntimeError("unknown op "+op)
    return outbox,it

if __name__=='__main__':
    pass
