/****************************************************************************

    ORDER.H - order records, wares catalog, config and Giro payment logic.

    Pure data logic: NO serial/UI output.  File I/O uses the Windows 1.01
    KERNEL file API (OpenFile + low-level _lread/_lwrite/_lclose/_llseek) --
    these ARE present in 1.01 (KERNEL ordinals 74/82/86/81/84) and are what
    the shipped apps use; the C run-time low-level _open/_read/... are NOT in
    C:\WINLIB.10 and must not be linked (see ORDER.C / docs/win101-loader.md).
    Every interface here is plain NEAR `char *`; only the KERNEL calls inside
    ORDER.C cast to LPSTR.  Data files are opened by absolute D: path (the
    guest CWD is C:\WINDOWS).  Catalog/order text is CP865 on disk; this
    module copies those bytes verbatim and never interprets them.

****************************************************************************/

#define ORD_MAXITEMS 20

typedef struct {
    char artikel[4];        /* article number, e.g. "101" + NUL */
    char navn[35];          /* name from VARER.TXT (<=34 CP865 bytes + NUL) */
    int  pris;              /* unit price, kr */
    int  antal;             /* quantity */
} ORDLINE;

typedef struct {
    char id[16];            /* date-based numeric id, <=15 digits + NUL */
    char status[12];        /* NY | AFVENTER | ACCEPTERET | ACCEPTFEJL | AFVIST | LEVERET */
    char created[16];       /* "YYYYMMDDHHMM" */
    char accepted[16];      /* reserved; "-" until set by later work */
    char rejected[16];
    char delivered[16];
    char navn[31];
    char adresse[31];
    char postby[31];
    ORDLINE items[ORD_MAXITEMS];
    int  nItems;
    long total;             /* sum of pris*antal (long: guards 16-bit int) */
} ORDER;

/* Catalog (VARER.TXT). Get returns 1 while idx is valid, 0 past the end.
   Lookup returns 1 if the article number is found. name buffer >= 35. */
int  OrderCatalogGet(int idx, char *artOut, char *nameOut, int *prisOut);
int  OrderCatalogLookup(char *art, char *nameOut, int *prisOut);

/* Config: reads the ring-A config file. OpenFile ultimately hands the name to
   DOS, which uses the OEM codepage (CP865, ring-A = 0x8F); dosbox maps the
   host's UTF-8 ring INI filename to exactly that name. Fills out8 with an
   8-digit account; returns 1 if configured, 0 if missing/invalid (out8 =
   "00000000"). out8 buffer >= 9. */
int  OrderGetKreditor(char *out8);

/* Admin gate: 1 iff [Admin] Kodeord is configured in the INI AND pw matches it
   exactly (case-sensitive); 0 otherwise (missing/blank key -> access denied).
   Reads the same ring-A INI as OrderGetKreditor. */
int  OrderCheckAdmin(char *pw);

/* Date-based order id (YYYYMMDD + 3-digit daily sequence). idOut buffer >= 16. */
void OrderMakeId(char *idOut);

/* Current local time as "YYYYMMDDHHMM". out buffer >= 13. */
void OrderTimestamp(char *out);

/* Giro +04: check digit of 15 payload digits; full code line into out (>=40). */
int  OrderGiroCheck(char *d15);
void OrderGiroLine(char *out, char *id, char *kreditor8);

/* Orders file (ORDRER.TXT). Append one order; find by id; iterate by index. */
int  OrderAppend(ORDER *o);
int  OrderFind(char *id, ORDER *o);
int  OrderGetByIndex(int idx, ORDER *o);   /* 1 while idx valid, 0 past end */

/* Change an order's status (rewrites ORDRER.TXT) and stamp the matching
   timestamp: ACCEPTERET->accepted, AFVIST->rejected, LEVERET->delivered.
   1 if found+updated, 0 otherwise. Customer/item bytes are preserved verbatim. */
int  OrderSetStatus(char *id, char *newStatus);

/* Register a callback invoked synchronously whenever an order is appended
   (OrderAppend). Same process, so the GUI just refreshes its list in the
   call -- no polling. Pass 0 to clear. */
void OrderOnChange(void (*fn)(void));
