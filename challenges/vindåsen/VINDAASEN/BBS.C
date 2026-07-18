/****************************************************************************

    BBS.C - menu-driven ANSI ordering interface for the VINDAASEN line.

    A screen/state machine over the serial line.  UI only: all persistence,
    catalog, config, id and Giro math live in ORDER.C; this module drives the
    conversation and renders results.  Output is ANSI/VT100 (clear-screen,
    colour, CP865 box-drawing).  The order being built lives in `curOrder`.

    Flow: menu -> N: Navn/Adresse/Postnr og by -> catalog -> loop(Varenr,Antal)
    -> summary with order id + Giro +04 code line.  S: status by order id.

    WIRE ENCODING: Danish text and box-drawing are CP865 single bytes; ANSI
    escapes are ASCII.  Keep this file saved as CP865 (distinct from the
    CP1252 GUI).

****************************************************************************/

#include <windows.h>
#include <string.h>
#include "comm.h"
#include "bbs.h"
#include "order.h"
#include "link.h"
#include "admin.h"

#define ESC     "\x1b"
#define CLS     ESC "[2J" ESC "[H"
#define CYAN    ESC "[36m"
#define RESET   ESC "[0m"

#define ST_MENU       0
#define ST_NAVN       1
#define ST_ADRESSE    2
#define ST_POSTBY     3
#define ST_ART        4
#define ST_QTY        5
#define ST_STATUS_ID  6
#define ST_PAUSE      7
#define ST_ADMIN_MENU  8
#define ST_ADMIN_PAUSE 9
#define ST_ADMIN_UPDATE 10

#define FLDMAX 30       /* max chars of line input (fits ORDER 31-byte fields) */

static BOOL    fGreeted = FALSE;
static int     state    = ST_MENU;
static char    field[64];
static int     fieldLen = 0;
static ORDER   curOrder;        /* order being built */
static ORDER   tmpOrder;        /* status lookup / list */
static ORDLINE pend;            /* item awaiting its quantity */
static int     starCount = 0;   /* consecutive * at main menu = admin trigger */

/* ---- output helpers ----------------------------------------------------- */

static void Say(LPSTR sz)
{
    int n = 0;
    while (sz[n]) n++;
    CommSend(sz, n);
}

static void SayLn(LPSTR sz)
{
    Say(sz);
    Say((LPSTR)"\r\n");
}

static void SayInt(int v)
{
    char b[7];
    int  i = 6;
    b[6] = '\0';
    if (v == 0) { Say((LPSTR)"0"); return; }
    while (v > 0 && i > 0) { b[--i] = (char)('0' + (v % 10)); v /= 10; }
    Say((LPSTR)&b[i]);
}

static void SayLong(long v)
{
    char b[12];
    int  i = 11;
    b[11] = '\0';
    if (v == 0) { Say((LPSTR)"0"); return; }
    while (v > 0 && i > 0) { b[--i] = (char)('0' + (int)(v % 10)); v /= 10; }
    Say((LPSTR)&b[i]);
}

static int Atoi(LPSTR s)
{
    int v = 0, i = 0;
    while (s[i] >= '0' && s[i] <= '9') { v = v * 10 + (s[i] - '0'); i++; }
    return v;
}

/* One char of normal line input: echo it, handle backspace; return 1 when Enter
   is pressed.  Accepts any printable byte INCLUDING CP865 high-bit letters
   (0x86 = a-ring, 0x91 = ae, 0x9b = oe, ...); char is signed in QuickC, so a
   plain `c >= ' '` is false for 0x80..0xFF and would silently drop every Danish
   character -- compare as unsigned. */
static int LineChar(char c)
{
    if (c == '\r' || c == '\n') { Say((LPSTR)"\r\n"); return 1; }
    if (c == '\b' || c == 0x7f) {
        if (fieldLen > 0) { fieldLen--; Say((LPSTR)"\b \b"); }
        return 0;
    }
    if ((unsigned char)c >= ' ' && fieldLen < FLDMAX) {
        field[fieldLen++] = c;
        CommSend((LPSTR)&c, 1);                    /* echo the character */
    }
    return 0;
}

/* Replace the field delimiters ('|', ';') so free text can't corrupt the
   orders-file line format. */
static void SanitizeField(void)
{
    int i;
    for (i = 0; i < fieldLen; i++)
        if (field[i] == '|' || field[i] == ';') field[i] = ' ';
}

/* ---- screens ------------------------------------------------------------ */

static void DrawMenu(void)
{
    Say((LPSTR)CLS);
    Say((LPSTR)"\r\n\r\n");
    Say((LPSTR)CYAN);
    SayLn((LPSTR)"        ÉÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍ»");
    SayLn((LPSTR)"        º    VINDSEN ORDRESYSTEM    º");
    SayLn((LPSTR)"        ÈÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍ¼");
    Say((LPSTR)RESET);
    SayLn((LPSTR)"");
    SayLn((LPSTR)"           N)  Ny bestilling");
    SayLn((LPSTR)"           S)  Status p† ordre");
    SayLn((LPSTR)"           A)  Afslut");
    SayLn((LPSTR)"");
    Say((LPSTR)"        V‘lg: ");
    state = ST_MENU;
    fieldLen = 0;
}

static void Greet(void)
{
    DrawMenu();
    fGreeted = TRUE;
}

static void StartNewOrder(void)
{
    curOrder.nItems = 0;
    curOrder.navn[0] = '\0';
    curOrder.adresse[0] = '\0';
    curOrder.postby[0] = '\0';
    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Ny bestilling");
    SayLn((LPSTR)"  =============");
    SayLn((LPSTR)"");
    Say((LPSTR)"  Navn: ");
    fieldLen = 0;
    state = ST_NAVN;
}

static void ShowCatalog(void)
{
    char art[4], nm[35];
    int  pris, idx = 0;

    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Varekatalog");
    SayLn((LPSTR)"  ===========");
    SayLn((LPSTR)"");
    while (OrderCatalogGet(idx, art, nm, &pris)) {
        Say((LPSTR)"   ");
        Say((LPSTR)art);
        Say((LPSTR)"  ");
        Say((LPSTR)nm);
        Say((LPSTR)"  ");
        SayInt(pris);
        SayLn((LPSTR)" kr.");
        idx++;
    }
    if (idx == 0) SayLn((LPSTR)"  (katalog utilg‘ngeligt)");
    SayLn((LPSTR)"");
    Say((LPSTR)"  Varenr (blank=slut): ");
}

static void FinishOrder(void)
{
    char giro[48], k8[9];
    int  i, kok;
    long lsum;

    if (curOrder.nItems == 0) {
        Say((LPSTR)CLS);
        SayLn((LPSTR)"  Ingen varer valgt - annulleret.");
        SayLn((LPSTR)"");
        Say((LPSTR)"  Tryk en tast for menu...");
        state = ST_PAUSE;
        return;
    }

    curOrder.total = 0;
    for (i = 0; i < curOrder.nItems; i++)
        curOrder.total += (long)curOrder.items[i].pris * curOrder.items[i].antal;

    OrderMakeId(curOrder.id);
    OrderTimestamp(curOrder.created);
    strcpy(curOrder.status,    "NY");
    strcpy(curOrder.accepted,  "-");
    strcpy(curOrder.rejected,  "-");
    strcpy(curOrder.delivered, "-");
    kok = OrderGetKreditor(k8);
    OrderGiroLine(giro, curOrder.id, k8);
    OrderAppend(&curOrder);

    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Bestilling modtaget - tak!");
    SayLn((LPSTR)"");
    Say((LPSTR)"  Navn:    "); SayLn((LPSTR)curOrder.navn);
    Say((LPSTR)"  Adresse: "); SayLn((LPSTR)curOrder.adresse);
    Say((LPSTR)"           "); SayLn((LPSTR)curOrder.postby);
    SayLn((LPSTR)"");
    for (i = 0; i < curOrder.nItems; i++) {
        lsum = (long)curOrder.items[i].pris * curOrder.items[i].antal;
        Say((LPSTR)"   ");
        SayInt(curOrder.items[i].antal);
        Say((LPSTR)" x ");
        Say((LPSTR)curOrder.items[i].navn);
        Say((LPSTR)"  = ");
        SayLong(lsum);
        SayLn((LPSTR)" kr.");
    }
    SayLn((LPSTR)"");
    Say((LPSTR)"  I alt: "); SayLong(curOrder.total); SayLn((LPSTR)" kr.");
    SayLn((LPSTR)"");
    Say((LPSTR)"  Ordrenr: "); SayLn((LPSTR)curOrder.id);
    SayLn((LPSTR)"  Betal via girokort (+04):");
    Say((LPSTR)"    "); SayLn((LPSTR)giro);
    if (!kok) SayLn((LPSTR)"  ** Girokonto ikke konfigureret **");
    SayLn((LPSTR)"");
    Say((LPSTR)"  Tryk en tast for menu...");
    state = ST_PAUSE;
}

static void ShowList(void)
{
    int idx = 0;

    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Bestillinger");
    SayLn((LPSTR)"  ============");
    SayLn((LPSTR)"");
    if (!OrderGetByIndex(0, &tmpOrder)) {
        SayLn((LPSTR)"  Ingen bestillinger endnu.");
    } else {
        while (OrderGetByIndex(idx, &tmpOrder)) {
            Say((LPSTR)"   ");
            Say((LPSTR)tmpOrder.id);
            Say((LPSTR)"  ");
            Say((LPSTR)tmpOrder.status);
            Say((LPSTR)"  ");
            SayLn((LPSTR)tmpOrder.navn);
            idx++;
        }
    }
    SayLn((LPSTR)"");
    Say((LPSTR)"  Tryk en tast for menu...");
    state = ST_PAUSE;
}

static void StartStatus(void)
{
    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Status p† ordre");
    SayLn((LPSTR)"  ===============");
    SayLn((LPSTR)"");
    Say((LPSTR)"  Ordrenr: ");
    fieldLen = 0;
    state = ST_STATUS_ID;
}

static void DrawStatus(ORDER *o)
{
    int i;
    SayLn((LPSTR)"");
    Say((LPSTR)"  Ordrenr:  "); SayLn((LPSTR)o->id);
    Say((LPSTR)"  Status:   "); SayLn((LPSTR)o->status);
    Say((LPSTR)"  Oprettet: "); SayLn((LPSTR)o->created);
    Say((LPSTR)"  Navn:     "); SayLn((LPSTR)o->navn);
    SayLn((LPSTR)"");
    for (i = 0; i < o->nItems; i++) {
        Say((LPSTR)"   ");
        SayInt(o->items[i].antal);
        Say((LPSTR)" x ");
        SayLn((LPSTR)o->items[i].navn);
    }
    Say((LPSTR)"  I alt: "); SayLong(o->total); SayLn((LPSTR)" kr.");
}

static void Goodbye(void)
{
    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Farvel!");
    SayLn((LPSTR)"");
    Say((LPSTR)"  Tryk en tast...");
    state = ST_PAUSE;
}


static void DrawAdminMenu(void)
{
    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Administration");
    SayLn((LPSTR)"  =============");
    SayLn((LPSTR)"");
    SayLn((LPSTR)"   V)  Vis bestillinger");
    SayLn((LPSTR)"   O)  Opdater leverance-tjeneste");
    SayLn((LPSTR)"   T)  Tilbage");
    SayLn((LPSTR)"");
    Say((LPSTR)"  V‘lg: ");
    starCount = 0;
    state = ST_ADMIN_MENU;
}

static void StartUpdate(void)
{
    Say((LPSTR)CLS);
    SayLn((LPSTR)"  Opdater leverance-tjeneste");
    SayLn((LPSTR)"  =========================");
    SayLn((LPSTR)"");
    SayLn((LPSTR)"  Send ny VDLEV.EXE som hex (16 bytes/linje).");
    SayLn((LPSTR)"  Afslut med EOT (Ctrl-D).");
    SayLn((LPSTR)"");
    LinkSendLine("OPDATER");   /* tell the monitor a new image follows */
    fieldLen = 0;
    state = ST_ADMIN_UPDATE;
}

/* Drain COM3 output back to the BBS terminal for up to 10 s.
   Called after the admin firmware-upload EOT; the new VDLEV service
   (which contestants build) kills VDLOVV, claims COM2, and sends any
   data it likes -- this window echoes it to the attacker on COM2. */
static void ReadUpdateResponse(void)
{
    DWORD deadline = GetCurrentTime() + 10000L;
    char c;
    Say((LPSTR)"\r\n  Venter svar fra tjeneste...\r\n");
    while (GetCurrentTime() < deadline) {
        if (LinkReadByte(&c)) CommSend((LPSTR)&c, 1);
    }
    SayLn((LPSTR)"");
    Say((LPSTR)"\r\n  Tryk en tast for menu...");
    state = ST_ADMIN_PAUSE;
}

static void MenuKey(char c)
{
    if      (c == 'N' || c == 'n') StartNewOrder();
    else if (c == 'S' || c == 's') StartStatus();
    else if (c == 'A' || c == 'a') Goodbye();
    /* else ignore */
}

/* ---- entry points ------------------------------------------------------- */

void BbsReset(void)
{
    fGreeted = FALSE;
    state = ST_MENU;
    fieldLen = 0;
    starCount = 0;
}

void BbsConnect(void)
{
    BbsReset();
    Greet();
}

void BbsReceive(LPSTR buf, int cb)
{
    int  i;
    char c;

    if (!fGreeted)
        Greet();

    for (i = 0; i < cb; i++) {
        c = buf[i];
        switch (state) {
            case ST_MENU:
                if (c == '*') {
                    if (++starCount >= 6) { starCount = 0; if (StartAdminLogin()) DrawAdminMenu(); else state = ST_PAUSE; }
                } else {
                    starCount = 0;
                    MenuKey(c);
                }
                break;

            case ST_NAVN:
                if (LineChar(c)) {
                    field[fieldLen] = '\0'; SanitizeField();
                    strcpy(curOrder.navn, field);
                    Say((LPSTR)"  Adresse: ");
                    fieldLen = 0; state = ST_ADRESSE;
                }
                break;

            case ST_ADRESSE:
                if (LineChar(c)) {
                    field[fieldLen] = '\0'; SanitizeField();
                    strcpy(curOrder.adresse, field);
                    Say((LPSTR)"  Postnr og by: ");
                    fieldLen = 0; state = ST_POSTBY;
                }
                break;

            case ST_POSTBY:
                if (LineChar(c)) {
                    field[fieldLen] = '\0'; SanitizeField();
                    strcpy(curOrder.postby, field);
                    ShowCatalog();
                    fieldLen = 0; state = ST_ART;
                }
                break;

            case ST_ART:
                if (LineChar(c)) {
                    field[fieldLen] = '\0';
                    if (fieldLen == 0) {
                        FinishOrder();
                    } else if (OrderCatalogLookup(field, pend.navn, &pend.pris)) {
                        strcpy(pend.artikel, field);
                        Say((LPSTR)"  Antal: ");
                        fieldLen = 0; state = ST_QTY;
                    } else {
                        Say((LPSTR)"  Ukendt varenummer.\r\n  Varenr (blank=slut): ");
                        fieldLen = 0;
                    }
                }
                break;

            case ST_QTY:
                if (LineChar(c)) {
                    int antal;
                    field[fieldLen] = '\0';
                    antal = Atoi((LPSTR)field);
                    if (antal < 1) {
                        Say((LPSTR)"  Ugyldigt antal.\r\n  Antal: ");
                        fieldLen = 0;
                    } else if (curOrder.nItems >= ORD_MAXITEMS) {
                        Say((LPSTR)"  Ordren er fuld.\r\n");
                        FinishOrder();
                    } else {
                        pend.antal = antal;
                        curOrder.items[curOrder.nItems] = pend;
                        curOrder.nItems++;
                        Say((LPSTR)"  Tilf›jet.\r\n  Varenr (blank=slut): ");
                        fieldLen = 0; state = ST_ART;
                    }
                }
                break;

            case ST_STATUS_ID:
                if (LineChar(c)) {
                    field[fieldLen] = '\0';
                    if (OrderFind(field, &tmpOrder)) DrawStatus(&tmpOrder);
                    else Say((LPSTR)"\r\n  Ukendt ordre.\r\n");
                    Say((LPSTR)"\r\n  Tryk en tast for menu...");
                    state = ST_PAUSE;
                }
                break;

            case ST_ADMIN_MENU:
                if (c == 'V' || c == 'v') { ShowList(); state = ST_ADMIN_PAUSE; }
                else if (c == 'O' || c == 'o') { StartUpdate(); }
                else if (c == 'T' || c == 't') DrawMenu();
                /* else ignore */
                break;

            case ST_ADMIN_UPDATE:
                /* forward the admin hex stream to the monitor on COM3;
                   0x04 (EOT) ends it -- do NOT echo (throughput). */
                if (c == 0x04) {
                    LinkSendLine("EOT");
                    SayLn((LPSTR)"");
                    SayLn((LPSTR)"  Opdatering sendt.");
                    ReadUpdateResponse();
                } else {
                    LinkSendRaw(&c, 1);
                }
                break;

            case ST_ADMIN_PAUSE:
                DrawAdminMenu();
                break;

            case ST_PAUSE:
                DrawMenu();
                break;
        }
    }
}
