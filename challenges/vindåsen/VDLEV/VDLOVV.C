/****************************************************************************

    VDLOVV.C - VinDaasen Leverance Overvaager (fulfilment MONITOR).

    Runs on the fulfilment Windows 1.01 machine (2nd dosbox instance).  Owns
    the serial link to the main app on COM2 (Windows comm API, 1200-8N1, via
    the copied COMM.C) and relays to the service app VDLEV via Windows
    messages.  Wire protocol (the far side of the main app's COM3 link,
    line-oriented plain text): IN  ORDRE|<id>|... ; OUT KVITTER <id> /
    LEVERET <id>.  The service (VDLEV) decides ack/deliver and posts them back
    here; VDLOVV just relays.  The order id travels between the two apps split
    across wParam(seq)+lParam(date) -- see VDLINK.H.  ASCII source: only ASCII
    order ids are handled here, never CP865 customer text.

    Remote update: the main app can push a new service image over the same COM2
    line -- IN  OPDATER, then hex lines (16 bytes each), then EOT.  VDLOVV writes
    the decoded bytes to a scratch file, stops the running VDLEV (WM_CLOSE),
    waits for it to unload, renames the scratch over VDLEV.EXE, and relaunches
    it (LoadModule -- WinExec is absent from the 1.x import libs).

****************************************************************************/

#include <windows.h>
#include <string.h>
#include <dos.h>                /* intdosx / segread -- DOS rename (INT 21h 56h) */
#include "vdlink.h"
#include "comm.h"

HANDLE hInst;

static HWND hLog = NULL;
#define IDC_LOG   100
#define ID_TIMER  1
#define TIMER_MS  100

/* ---- remote update of the service (VDLEV.EXE) --------------------------- */
#define F_NEW  "D:\\VDLEVNEW.EXE"    /* scratch: the incoming image */
#define F_CUR  "D:\\VDLEV.EXE"       /* the live service exe */
#define UPD_IDLE       0
#define UPD_RECV       1             /* writing hex-decoded bytes to F_NEW */
#define UPD_WAITCLOSE  2             /* asked VDLEV to close; waiting to swap */
#define CLOSE_MS   8000UL            /* give the service this long to exit */

static int   updState    = UPD_IDLE;
static int   updFile     = -1;       /* OpenFile handle for F_NEW while receiving */
static long  updBytes    = 0;
static DWORD updDeadline = 0;

long FAR PASCAL MainWndProc(HWND, unsigned, WORD, LONG);
static void PollComm(void);

static int startsWith(char *s, char *p) { while (*p) { if (*s++ != *p++) return 0; } return 1; }

/* split a decimal id string into date (first 8 digits) + seq (the rest) */
static void IdSplit(char *id, long *date, WORD *seq)
{
    long d = 0; unsigned s = 0; int i = 0;
    for (; i < 8 && id[i]; i++) d = d * 10 + (id[i] - '0');
    for (; id[i]; i++)          s = s * 10 + (id[i] - '0');
    *date = d; *seq = (WORD)s;
}

/* append one line to the log listbox and scroll it into view */
static void Log(char *s)
{
    if (!hLog) return;
    SendMessage(hLog, LB_ADDSTRING, 0, (LONG)(LPSTR)s);
    SendMessage(hLog, LB_SETCURSEL,
                (WORD)(SendMessage(hLog, LB_GETCOUNT, 0, 0L) - 1), 0L);
}

/* ---- COM2 line assembly + relay to VDLEV ------------------------------- */

static char linebuf[256];
static int  linelen = 0;

/* ---- remote-update helpers (OPDATER ... hex ... EOT over COM2) ---------- */

static char *AppI(char *d, long v)      /* append a decimal long, return end */
{
    char t[12]; int k = 0;
    if (v < 0) { *d++ = '-'; v = -v; }
    if (v == 0) t[k++] = '0';
    while (v > 0) { t[k++] = (char)('0' + (int)(v % 10)); v /= 10; }
    while (k > 0) *d++ = t[--k];
    *d = 0; return d;
}

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

/* decode a hex line into bytes; returns the count, or -1 if the line holds a
   non-hex/non-space char or an odd digit count (so a stray line -- e.g. an
   interleaved ORDRE| -- can't corrupt the image). */
static int HexLine(char *s, unsigned char *out, int max)
{
    int n = 0, hi = -1, v;
    while (*s && n < max) {
        if (*s == ' ' || *s == '\t' || *s == '\r') { s++; continue; }
        v = hexval(*s++);
        if (v < 0) return -1;
        if (hi < 0) hi = v;
        else { out[n++] = (unsigned char)((hi << 4) | v); hi = -1; }
    }
    if (hi >= 0) return -1;                 /* trailing half-byte */
    return n;
}

static void UpdBegin(void)                  /* OPDATER: open the scratch file */
{
    OFSTRUCT of;
    if (updFile >= 0) { _lclose(updFile); updFile = -1; }   /* restart if mid-flight */
    updFile  = OpenFile((LPSTR)F_NEW, (LPOFSTRUCT)&of, OF_CREATE);   /* truncates */
    updBytes = 0;
    if (updFile < 0) { Log("Kan ikke oprette VDLEVNEW.EXE"); updState = UPD_IDLE; return; }
    updState = UPD_RECV;
    Log("Modtager ny VDLEV.EXE...");
}

static void UpdData(char *s)                /* one hex line -> bytes -> file */
{
    unsigned char bin[24];
    int n;
    if (updFile < 0) return;
    n = HexLine(s, bin, sizeof(bin));
    if (n < 0) return;                      /* stray/interleaved line: skip */
    if (n > 0) { _lwrite(updFile, (LPSTR)bin, n); updBytes += n; }
}

static void UpdFinishRecv(void)             /* EOT: close file, ask VDLEV to quit */
{
    char m[48], *q;
    HWND hSvc;
    if (updFile >= 0) { _lclose(updFile); updFile = -1; }
    q = m; strcpy(q, "Modtaget "); while (*q) q++;
    q = AppI(q, updBytes);
    strcpy(q, " bytes, stopper VDLEV");
    Log(m);
    hSvc = FindWindow((LPSTR)VDLEV_CLASS, (LPSTR)NULL);
    if (hSvc) PostMessage(hSvc, WM_CLOSE, 0, 0L);
    updState    = UPD_WAITCLOSE;
    updDeadline = GetCurrentTime() + CLOSE_MS;
}

static void HandleLine(char *s)
{
    char id[16], msg[32], *p;
    HWND hSvc;
    long date;
    WORD seq;
    int  j;

    if (updState == UPD_RECV) {                  /* firmware upload in progress */
        if (strcmp(s, "EOT") == 0) UpdFinishRecv();
        else                       UpdData(s);
        return;
    }
    if (startsWith(s, "OPDATER")) { UpdBegin(); return; }

    if (!startsWith(s, "ORDRE|")) return;        /* only order lines matter */
    p = s + 6; j = 0;
    while (*p && *p != '|' && j < 15) id[j++] = *p++;
    id[j] = 0;

    strcpy(msg, "ORDRE "); strcat(msg, id);
    Log(msg);

    hSvc = FindWindow((LPSTR)VDLEV_CLASS, (LPSTR)NULL);
    if (hSvc) {
        IdSplit(id, &date, &seq);
        PostMessage(hSvc, WM_VDL_ORDER, seq, date);
    } else {
        Log("(VDLEV ikke fundet)");
    }
}

static void LineByte(unsigned char c)
{
    if (c == '\n') { linebuf[linelen] = 0; if (linelen) HandleLine(linebuf); linelen = 0; }
    else if (c == '\r') { /* strip */ }
    else if (linelen < (int)sizeof(linebuf) - 1) linebuf[linelen++] = (char)c;
}

static void PollComm(void)
{
    char buf[128];
    int  n, i;
    while ((n = CommRead((LPSTR)buf, sizeof(buf))) > 0)
        for (i = 0; i < n; i++) LineByte((unsigned char)buf[i]);
}

/* send "<kw> <id>\r\n" on COM2 for the id rebuilt from a message, and log it */
static void Reply(char *kw, WORD seq, long date)
{
    char id[16], line[40];
    VdlIdStr(id, date, seq);
    strcpy(line, kw); strcat(line, " "); strcat(line, id);
    Log(line);
    strcat(line, "\r\n");
    CommSend((LPSTR)line, (int)strlen(line));
}

/* ---- the swap: delete old, rename scratch, relaunch -------------------- */

/* rename oldn -> newn via DOS INT 21h AH=56h (no C-runtime rename, which
   would drag in the C file library and set NEIERR).  Small model: both names
   are near, so DS=ES=DGROUP via segread. */
static int DosRename(char *oldn, char *newn)
{
    union REGS   r;
    struct SREGS sr;
    segread(&sr);
    r.h.ah = 0x56;
    r.x.dx = (unsigned)oldn;
    r.x.di = (unsigned)newn;
    intdosx(&r, &r, &sr);
    return r.x.cflag ? -1 : 0;
}

static void DoSwap(void)                    /* VDLEV has exited: replace + launch */
{
    OFSTRUCT of;
    HANDLE   h;
    WORD     showv[2];
    char     cmdline[2];
    struct { WORD segEnv; LPSTR lpCmdLine; LPSTR lpCmdShow; LPSTR lpReserved; } parms;

    OpenFile((LPSTR)F_CUR, (LPOFSTRUCT)&of, OF_DELETE);      /* drop the old exe */
    if (DosRename((char *)F_NEW, (char *)F_CUR) != 0) {
        Log("FEJL: kan ikke omdoebe VDLEVNEW.EXE");
        updState = UPD_IDLE;
        return;
    }
    cmdline[0] = 0; cmdline[1] = 0x0D;                       /* empty command tail */
    showv[0] = 2; showv[1] = SW_SHOWNORMAL;
    parms.segEnv     = 0;
    parms.lpCmdLine  = (LPSTR)cmdline;
    parms.lpCmdShow  = (LPSTR)showv;
    parms.lpReserved = (LPSTR)0;
    h = LoadModule((LPSTR)F_CUR, (LPVOID)&parms);            /* NOT WinExec (unlinkable) */
    if (h <= (HANDLE)32) Log("FEJL: kan ikke starte ny VDLEV.EXE");
    else                 Log("VDLEV opdateret og genstartet");
    updState = UPD_IDLE;
}

static void UpdTick(void)                   /* run each 100ms tick while WAITCLOSE */
{
    if (updState != UPD_WAITCLOSE) return;
    if (GetModuleHandle((LPSTR)"VDLEV") == NULL)            /* module fully unloaded */
        DoSwap();
    else if ((long)(GetCurrentTime() - updDeadline) >= 0) {
        Log("FEJL: VDLEV lukkede ikke - opdatering afbrudt");
        updState = UPD_IDLE;
    }
}

int PASCAL WinMain(HANDLE hInstance, HANDLE hPrev, LPSTR lpCmd, int nCmdShow)
{
    MSG      msg;
    WNDCLASS wc;
    HWND     hWnd;

    if (!hPrev) {
        wc.style         = CS_HREDRAW | CS_VREDRAW;
        wc.lpfnWndProc   = MainWndProc;
        wc.cbClsExtra    = 0;
        wc.cbWndExtra    = 0;
        wc.hInstance     = hInstance;
        wc.hIcon         = LoadIcon(NULL, IDI_APPLICATION);
        wc.hCursor       = LoadCursor(NULL, IDC_ARROW);
        wc.hbrBackground = GetStockObject(WHITE_BRUSH);
        wc.lpszMenuName  = NULL;
        wc.lpszClassName = (LPSTR)VDLOVV_CLASS;
        if (!RegisterClass(&wc)) return (FALSE);
    }
    hInst = hInstance;

    hWnd = CreateWindow((LPSTR)VDLOVV_CLASS, (LPSTR)"VinDaasen Leverance Overvaager",
        WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
        NULL, NULL, hInstance, NULL);
    if (!hWnd) return (FALSE);

    CommOpen();
    SetTimer(hWnd, ID_TIMER, TIMER_MS, NULL);
    ShowWindow(hWnd, nCmdShow);
    UpdateWindow(hWnd);

    while (GetMessage(&msg, NULL, NULL, NULL)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
        PollComm();
    }
    return (msg.wParam);
}

long FAR PASCAL MainWndProc(HWND hWnd, unsigned message, WORD wParam, LONG lParam)
{
    switch (message) {
        case WM_CREATE:
        {
            RECT rc;
            GetClientRect(hWnd, &rc);
            hLog = CreateWindow((LPSTR)"listbox", (LPSTR)NULL,
                WS_CHILD | WS_VISIBLE | WS_VSCROLL | WS_BORDER,
                0, 0, rc.right, rc.bottom, hWnd, (HMENU)IDC_LOG, hInst, (LPSTR)NULL);
            Log("VDLOVV klar - lytter paa COM2");
            break;
        }
        case WM_SIZE:
            if (hLog) MoveWindow(hLog, 0, 0, LOWORD(lParam), HIWORD(lParam), TRUE);
            break;
        case WM_TIMER:
            if (wParam == ID_TIMER) { PollComm(); UpdTick(); }
            break;
        case WM_VDL_ACK:
            Reply("KVITTER", wParam, lParam);
            break;
        case WM_VDL_DELIVERED:
            Reply("LEVERET", wParam, lParam);
            break;
        case WM_DESTROY:
            KillTimer(hWnd, ID_TIMER);
            CommClose();
            PostQuitMessage(0);
            break;
        default:
            return (DefWindowProc(hWnd, message, wParam, lParam));
    }
    return (0L);
}
