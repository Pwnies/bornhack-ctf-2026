/****************************************************************************

    ORDER.C - wares catalog, config, order id, Giro +04 math, persistence.

    File I/O uses the Windows 1.01 KERNEL file API -- OpenFile (ordinal 74)
    to open/create, then the low-level _lread/_lwrite/_lclose/_llseek (ords
    82/86/81/84) on the DOS handle it returns -- exactly the set the shipped
    1.01 apps (NOTEPAD, WRITE, ...) import.  These resolve as KERNEL ordinal
    imports at load time; no C file library is on the link line.
    Do NOT use the C run-time low-level _open/_read/_write/_close/_creat:
    those symbols are absent from C:\WINLIB.10, so linking them leaves
    unresolved externals and LINK marks the NE "errors in image" (NEIERR,
    0x2000) -- the 1.01 loader then refuses the exe and the MSDOS Executive
    shows the misleading "Not enough memory to run".  (See docs/win101-loader.md.)

    _lread/_lwrite take LPSTR (far); in -AS small model the near g_buf is
    cast (LPSTR).  _lread returns WORD (0xFFFF on error) -> assigning to int
    yields -1, so the "n <= 0" loop test still works.

    No <stdio.h>/printf (too large; numbers formatted by hand via PutNum).
    NEAR char* throughout (-AS small model).  Data files opened by absolute
    D: path (guest CWD is C:\WINDOWS).  Catalog/order text is CP865 on disk
    and copied verbatim.  ASCII source; the only escaped high byte is \x8F
    (ring-A) in the INI filename.

****************************************************************************/

#include <windows.h>            /* _lopen/_lread/_lwrite/_lclose/_lcreat/_llseek */
#include <time.h>
#include <string.h>
#include "order.h"

#define F_VARER   "D:\\VARER.TXT"
#define F_ORDRER  "D:\\ORDRER.TXT"
/* Config file has a ring-A. OpenFile hands the name to DOS, which uses the OEM
   codepage (CP865, ring-A = 0x8F); dosbox maps the host's UTF-8 ring INI
   filename to exactly that name (verified), so no other spelling is tried. */
#define F_INI  "D:\\VIND\x8FSEN.INI"        /* CP865 ring-A */

/* Whole-file read buffer.  Kept modest; the orders file is assumed to stay
   well under this ("very limited orders"). */
static char g_buf[2048];

/* ---- small helpers ------------------------------------------------------ */

static int isdig(char c) { return (c >= '0' && c <= '9'); }

/* append s to d, return new end (no NUL written) */
static char *PutStr(char *d, char *s) { while (*s) *d++ = *s++; return d; }

/* append v as decimal, zero-padded to at least `width` digits; return end. */
static char *PutNum(char *d, long v, int width)
{
    char t[12];
    int  n = 0, i;
    if (v < 0) { *d++ = '-'; v = -v; }
    if (v == 0) t[n++] = '0';
    while (v > 0) { t[n++] = (char)('0' + (int)(v % 10)); v /= 10; }
    for (i = n; i < width; i++) *d++ = '0';
    while (n > 0) *d++ = t[--n];
    return d;
}

static long Atol(char *s)
{
    long v = 0; int i = 0;
    while (isdig(s[i])) { v = v * 10 + (s[i] - '0'); i++; }
    return v;
}

static int ceq(char a, char b)
{
    if (a >= 'a' && a <= 'z') a = (char)(a - 32);
    if (b >= 'a' && b <= 'z') b = (char)(b - 32);
    return a == b;
}

/* Read an entire file into g_buf via OpenFile + low-level _lread.
   Returns byte count (>=0, g_buf NUL-terminated) or -1 if it can't open. */
static int ReadWhole(char *name)
{
    OFSTRUCT of;
    int h, n, total = 0;

    h = OpenFile((LPSTR)name, (LPOFSTRUCT)&of, OF_READ);
    if (h < 0) return -1;
    while (total < (int)sizeof(g_buf) - 1) {
        n = _lread(h, (LPSTR)(g_buf + total),
                   (int)(sizeof(g_buf) - 1 - total));
        if (n <= 0) break;
        total += n;
    }
    _lclose(h);
    g_buf[total] = '\0';
    return total;
}

/* Extract the next line from *pp into out (strip trailing CR); advance *pp.
   Returns 1 if a line was produced, 0 at end of buffer. */
static int NextLine(char **pp, char *out, int max)
{
    char *p = *pp;
    int   n = 0;

    if (!p || *p == '\0') return 0;
    while (*p && *p != '\n' && n < max - 1) out[n++] = *p++;
    if (n > 0 && out[n-1] == '\r') n--;
    out[n] = '\0';
    while (*p && *p != '\n') p++;
    if (*p == '\n') p++;
    *pp = p;
    return 1;
}

/* ---- catalog (VARER.TXT) ------------------------------------------------ */

/* article = first 3 chars; price = trailing digit run; name = span between. */
static int ParseVare(char *line, char *art, char *name, int *pris)
{
    int len, ps, ne, i, j;

    len = 0; while (line[len]) len++;
    if (len < 6 || !isdig(line[0])) return 0;

    art[0] = line[0]; art[1] = line[1]; art[2] = line[2]; art[3] = '\0';

    while (len > 0 && line[len-1] == ' ') len--;
    ps = len; while (ps > 0 && isdig(line[ps-1])) ps--;
    *pris = 0; i = ps; while (i < len) { *pris = *pris * 10 + (line[i]-'0'); i++; }

    ne = ps; while (ne > 5 && line[ne-1] == ' ') ne--;
    j = 0; i = 5; while (i < ne && j < 34) name[j++] = line[i++];
    name[j] = '\0';
    return 1;
}

int OrderCatalogGet(int idx, char *art, char *name, int *pris)
{
    char *p, line[128];
    int   i = 0;

    if (ReadWhole(F_VARER) < 0) return 0;
    p = g_buf;
    while (NextLine(&p, line, sizeof(line))) {
        if (!ParseVare(line, art, name, pris)) continue;
        if (i == idx) return 1;
        i++;
    }
    return 0;
}

int OrderCatalogLookup(char *artQ, char *name, int *pris)
{
    char *p, line[128], a[4], nm[35];
    int   pr;

    if (ReadWhole(F_VARER) < 0) return 0;
    p = g_buf;
    while (NextLine(&p, line, sizeof(line))) {
        if (!ParseVare(line, a, nm, &pr)) continue;
        if (strcmp(a, artQ) == 0) { strcpy(name, nm); *pris = pr; return 1; }
    }
    return 0;
}

/* ---- config (INI, parsed from g_buf) ------------------------------------ */

static int MatchBracket(char *p, char *sec)
{
    int i = 1, k = 0;
    while (p[i] && p[i] != ']') {
        if (sec[k] == '\0' || !ceq(p[i], sec[k])) return 0;
        i++; k++;
    }
    return (p[i] == ']' && sec[k] == '\0');
}

static int KeyMatch(char *p, char *key, char *out, int max)
{
    int i = 0, k = 0, n;
    while (key[k]) { if (!ceq(p[i], key[k])) return 0; i++; k++; }
    while (p[i] == ' ' || p[i] == '\t') i++;
    if (p[i] != '=') return 0;
    i++;
    while (p[i] == ' ' || p[i] == '\t') i++;
    n = 0; while (p[i] && n < max-1) out[n++] = p[i++];
    while (n > 0 && (out[n-1] == ' ' || out[n-1] == '\t')) n--;
    out[n] = '\0';
    return 1;
}

/* Find key in [section] within the already-loaded g_buf. 1 if found. */
static int IniParse(char *section, char *key, char *out, int max)
{
    char *p, line[256];
    int   inSect = 0, j;

    p = g_buf;
    while (NextLine(&p, line, sizeof(line))) {
        j = 0; while (line[j] == ' ' || line[j] == '\t') j++;
        if (line[j] == '[')      { inSect = MatchBracket(line + j, section); continue; }
        if (line[j] == ';' || line[j] == '\0') continue;
        if (!inSect) continue;
        if (KeyMatch(line + j, key, out, max)) return 1;
    }
    return 0;
}

int OrderGetKreditor(char *out8)
{
    char buf[32];
    int  i, len, pad, got = 0;

    buf[0] = '\0';
    if (ReadWhole(F_INI) >= 0 && IniParse("Giro", "Kreditornummer", buf, sizeof(buf)))
        got = 1;

    if (got) {
        len = 0; while (buf[len]) len++;
        if (len >= 1 && len <= 8) {
            int ok = 1;
            for (i = 0; i < len; i++) if (!isdig(buf[i])) ok = 0;
            if (ok) {
                pad = 8 - len;
                for (i = 0; i < pad; i++) out8[i] = '0';
                for (i = 0; i < len; i++) out8[pad+i] = buf[i];
                out8[8] = '\0';
                return 1;
            }
        }
    }
    for (i = 0; i < 8; i++) out8[i] = '0';
    out8[8] = '\0';
    return 0;
}

/* Admin password gate. 1 iff [Admin] Kodeord is configured and equals pw
   (exact, case-sensitive); 0 if unconfigured/blank/mismatch (deny). */
int OrderCheckAdmin(char *pw)
{
    char buf[40];

    if (ReadWhole(F_INI) >= 0 && IniParse("Admin", "Kodeord", buf, sizeof(buf))) {
        if (buf[0] == '\0') return 0;           /* configured but empty -> deny */
        return strcmp(buf, pw) == 0;
    }
    return 0;                                    /* not configured -> deny */
}

/* ---- order id (date-based YYYYMMDD + daily sequence) -------------------- */

void OrderMakeId(char *idOut)
{
    time_t     t;
    struct tm *lt;
    char       prefix[9], line[512], *p, *q;
    int        seq = 1, i, match;

    time(&t);
    lt = localtime(&t);
    q = prefix;
    q = PutNum(q, (long)(lt->tm_year + 1900), 4);
    q = PutNum(q, (long)(lt->tm_mon + 1), 2);
    q = PutNum(q, (long)lt->tm_mday, 2);
    *q = '\0';

    if (ReadWhole(F_ORDRER) >= 0) {
        p = g_buf;
        while (NextLine(&p, line, sizeof(line))) {
            match = 1;
            for (i = 0; i < 8; i++) if (line[i] != prefix[i]) { match = 0; break; }
            if (match) seq++;
        }
    }
    q = PutStr(idOut, prefix);
    q = PutNum(q, (long)seq, 3);
    *q = '\0';
}

void OrderTimestamp(char *out)
{
    time_t     t;
    struct tm *lt;
    char      *q = out;
    time(&t);
    lt = localtime(&t);
    q = PutNum(q, (long)(lt->tm_year + 1900), 4);
    q = PutNum(q, (long)(lt->tm_mon + 1), 2);
    q = PutNum(q, (long)lt->tm_mday, 2);
    q = PutNum(q, (long)lt->tm_hour, 2);
    q = PutNum(q, (long)lt->tm_min, 2);
    *q = '\0';
}

/* ---- Giro +04 ----------------------------------------------------------- */

int OrderGiroCheck(char *d15)
{
    int sum = 0, w = 2, i, p;
    for (i = 14; i >= 0; i--) {
        p = (d15[i] - '0') * w;
        if (p >= 10) p = (p / 10) + (p % 10);
        sum += p;
        w = (w == 2) ? 1 : 2;
    }
    return (10 - (sum % 10)) % 10;
}

void OrderGiroLine(char *out, char *id, char *k8)
{
    char pay[16];
    int  len, pad, i, chk;
    char *q;

    len = 0; while (id[len]) len++;
    if (len > 15) len = 15;
    pad = 15 - len;
    for (i = 0; i < pad; i++) pay[i] = '0';
    for (i = 0; i < len; i++) pay[pad+i] = id[i];
    pay[15] = '\0';

    chk = OrderGiroCheck(pay);
    q = out;
    q = PutStr(q, "+04<");
    q = PutStr(q, pay);
    *q++ = (char)('0' + chk);
    *q++ = '+';
    q = PutStr(q, k8);
    *q++ = '<';
    *q = '\0';
}

/* ---- persistence (ORDRER.TXT) ------------------------------------------ */

static char g_out[640];         /* order-line build buffer */
static void (*g_onChange)(void) = 0;   /* fired after an order is appended */

int OrderAppend(ORDER *o)
{
    OFSTRUCT of;
    char items[400];
    char *q;
    int  h, i, len;

    h = OpenFile((LPSTR)F_ORDRER, (LPOFSTRUCT)&of, OF_WRITE);  /* open existing... */
    if (h >= 0) _llseek(h, 0L, 2);                             /* ...seek to end (append) */
    else        h = OpenFile((LPSTR)F_ORDRER, (LPOFSTRUCT)&of, OF_CREATE);  /* or create */
    if (h < 0) return 0;

    q = items;
    for (i = 0; i < o->nItems; i++) {
        if (i > 0) *q++ = ';';
        q = PutStr(q, o->items[i].artikel);
        *q++ = '*';
        q = PutNum(q, (long)o->items[i].antal, 0);
    }
    *q = '\0';

    /* explicit CRLF: low-level _write does no text-mode translation */
    q = g_out;
    q = PutStr(q, o->id);        *q++ = '|';
    q = PutStr(q, o->status);    *q++ = '|';
    q = PutStr(q, o->created);   *q++ = '|';
    q = PutStr(q, o->accepted);  *q++ = '|';
    q = PutStr(q, o->rejected);  *q++ = '|';
    q = PutStr(q, o->delivered); *q++ = '|';
    q = PutStr(q, o->navn);      *q++ = '|';
    q = PutStr(q, o->adresse);   *q++ = '|';
    q = PutStr(q, o->postby);    *q++ = '|';
    q = PutStr(q, items);        *q++ = '|';
    q = PutNum(q, o->total, 0);
    *q++ = '\r'; *q++ = '\n';
    len = (int)(q - g_out);
    _lwrite(h, (LPSTR)g_out, len);
    _lclose(h);
    if (g_onChange) (*g_onChange)();   /* notify the GUI to refresh its list */
    return 1;
}

/* Register a callback fired after each successful OrderAppend. The GUI passes
   its list-refresh function so a BBS-created order appears immediately -- same
   process, a direct call, not a poll. */
void OrderOnChange(void (*fn)(void))
{
    g_onChange = fn;
}

/* Copy field from p up to '|' into out; return ptr past '|' or 0. */
static char *NextField(char *p, char *out, int max)
{
    int n = 0;
    if (!p) { out[0] = '\0'; return (char *)0; }
    while (*p && *p != '|' && n < max-1) out[n++] = *p++;
    out[n] = '\0';
    while (*p && *p != '|') p++;
    if (*p == '|') return p + 1;
    return (char *)0;
}

static void ParseItems(char *s, ORDER *o)
{
    o->nItems = 0;
    while (*s && o->nItems < ORD_MAXITEMS) {
        ORDLINE *it = &o->items[o->nItems];
        int n = 0;
        while (*s && *s != '*' && *s != ';' && n < 3) it->artikel[n++] = *s++;
        it->artikel[n] = '\0';
        it->antal = 0; it->pris = 0; it->navn[0] = '\0';
        if (*s == '*') { s++; while (isdig(*s)) { it->antal = it->antal*10 + (*s - '0'); s++; } }
        if (it->artikel[0]) {
            OrderCatalogLookup(it->artikel, it->navn, &it->pris);   /* reuses g_buf */
            o->nItems++;
        }
        if (*s == ';') s++;
    }
}

/* Parse one full order line (a local copy, NOT g_buf) into *o. */
static void ParseOrder(char *line, ORDER *o)
{
    char items[400], tot[16];
    char *p = line;

    p = NextField(p, o->id,        sizeof(o->id));
    p = NextField(p, o->status,    sizeof(o->status));
    p = NextField(p, o->created,   sizeof(o->created));
    p = NextField(p, o->accepted,  sizeof(o->accepted));
    p = NextField(p, o->rejected,  sizeof(o->rejected));
    p = NextField(p, o->delivered, sizeof(o->delivered));
    p = NextField(p, o->navn,      sizeof(o->navn));
    p = NextField(p, o->adresse,   sizeof(o->adresse));
    p = NextField(p, o->postby,    sizeof(o->postby));
    p = NextField(p, items,        sizeof(items));
    NextField(p, tot, sizeof(tot));
    o->total = Atol(tot);
    ParseItems(items, o);       /* overwrites g_buf, but `line` is a local copy */
}

int OrderFind(char *id, ORDER *o)
{
    char *p, line[512];
    int   i;

    if (ReadWhole(F_ORDRER) < 0) return 0;
    p = g_buf;
    while (NextLine(&p, line, sizeof(line))) {
        i = 0; while (id[i] && line[i] == id[i]) i++;
        if (id[i] == '\0' && (line[i] == '|' || line[i] == '\0')) {
            ParseOrder(line, o);    /* `line` is local; safe when g_buf is reused */
            return 1;
        }
    }
    return 0;
}

int OrderGetByIndex(int idx, ORDER *o)
{
    char *p, line[512];
    int   i = 0;

    if (ReadWhole(F_ORDRER) < 0) return 0;
    p = g_buf;
    while (NextLine(&p, line, sizeof(line))) {
        if (line[0] == '\0') continue;
        if (i == idx) {
            ParseOrder(line, o);    /* `line` is local; safe when g_buf is reused */
            return 1;
        }
        i++;
    }
    return 0;
}

/* Change one order's status in ORDRER.TXT and stamp the matching timestamp
   (ACCEPTERET->accepted, AFVIST->rejected, LEVERET->delivered).  Rewrites the
   whole file: reads it into g_buf, then truncates and writes every line back,
   substituting only the status (+timestamp) fields of the matching record.
   Deliberately does NOT parse items / look up the catalog -- that calls
   ReadWhole(VARER.TXT) which would clobber g_buf mid-rewrite; a field-level
   copy keeps every other byte (incl. CP865 customer text) verbatim.
   Returns 1 if the id was found and updated, 0 otherwise. */
int OrderSetStatus(char *id, char *newStatus)
{
    OFSTRUCT of;
    char *p, *fp, *nextfp, *q, *val;
    char  line[600], fld[420], out[700], ts[16];
    int   h, i, tsField, n, found = 0;

    n = ReadWhole(F_ORDRER);
    if (n < 0) return 0;
    if (n >= (int)sizeof(g_buf) - 1) return 0;   /* too big to rewrite safely */

    OrderTimestamp(ts);
    tsField = -1;
    if      (strcmp(newStatus, "ACCEPTERET") == 0) tsField = 3;
    else if (strcmp(newStatus, "AFVIST")     == 0) tsField = 4;
    else if (strcmp(newStatus, "LEVERET")    == 0) tsField = 5;

    h = OpenFile((LPSTR)F_ORDRER, (LPOFSTRUCT)&of, OF_CREATE);   /* truncate+rewrite */
    if (h < 0) return 0;

    p = g_buf;
    while (NextLine(&p, line, sizeof(line))) {
        if (line[0] == '\0') continue;
        i = 0; while (id[i] && line[i] == id[i]) i++;
        if (id[i] == '\0' && line[i] == '|') {
            q = out; fp = line;                 /* rewrite this record */
            for (i = 0; i < 11; i++) {
                nextfp = NextField(fp, fld, sizeof(fld));
                if      (i == 1)       val = newStatus;
                else if (i == tsField) val = ts;
                else                   val = fld;
                if (i > 0) *q++ = '|';
                q = PutStr(q, val);
                fp = nextfp;
                if (!fp && i < 10) break;        /* short/malformed line */
            }
            *q++ = '\r'; *q++ = '\n';
            _lwrite(h, (LPSTR)out, (int)(q - out));
            found = 1;
        } else {
            q = out;                             /* copy other lines verbatim */
            q = PutStr(q, line);
            *q++ = '\r'; *q++ = '\n';
            _lwrite(h, (LPSTR)out, (int)(q - out));
        }
    }
    _lclose(h);
    if (found && g_onChange) (*g_onChange)();   /* async status change -> refresh GUI */
    return found;
}
