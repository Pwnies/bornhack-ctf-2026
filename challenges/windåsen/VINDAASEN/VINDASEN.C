/****************************************************************************

    PROGRAM: VINDASEN.C

    PURPOSE: VINDAASEN takes and manages orders for canned wine.  It presents
             a BBS-like ordering interface over a COM port (COM2) and a GUI
             for managing orders.  This module owns the main window and the
             message loop; the serial line lives in COMM.C and the ordering
             session in BBS.C.

             Code and identifiers are English; GUI text is Danish (Windows
             ANSI / CP1252).

    FUNCTIONS:
             WinMain, InitApplication, InitInstance, MainWndProc, About,
             OrderDlgProc
             PollComm, FillOrderList, OpenSelectedOrder (static)

****************************************************************************/

#include <windows.h>
#include <string.h>
#include "vindasen.h"
#include "comm.h"
#include "bbs.h"
#include "order.h"
#include "link.h"

HANDLE hInst;   /* current instance */

#define MAXLIST 64
#define LIST_TOP 48             /* client y where the order list starts */
static HWND hOrderList = NULL;  /* order-list child (listbox) */
static char g_ids[MAXLIST][16]; /* list row -> order id */
static int  g_nList = 0;        /* rows currently listed */
static char g_selId[16];        /* order shown by the detail dialog */
static HANDLE hAccel = NULL;    /* accelerators: Enter=open, F5=refresh */
static HWND   hMainWnd = NULL;  /* main window (for TranslateAccelerator) */

static void PollComm(void);

/****************************************************************************
    Service the serial line: detect a caller connecting/hanging up (carrier
    change) and drain whatever bytes are buffered into the BBS.

    Called after every dispatched message AND from the WM_TIMER heartbeat.
    Both paths matter: a steady message stream would starve an "only when
    idle" poll, and the timer path keeps servicing the line during modal
    message loops (e.g. while the About dialog is up).  Everything here is
    non-blocking, so it is cheap when the line is quiet.
****************************************************************************/
static void PollComm(void)
{
    char buf[128];
    int  n;

    if (CommCarrierChanged())       /* caller connected or hung up */
        BbsConnect();               /* start a fresh, greeted session */

    while ((n = CommRead((LPSTR)buf, sizeof(buf))) > 0)
        BbsReceive((LPSTR)buf, n);

    LinkPoll();                     /* service the COM3 fulfilment link */
}

/* append a string / a decimal to a buffer; NUL-terminate; return the new end */
static char *AppS(char *d, char *s) { while (*s) *d++ = *s++; *d = 0; return d; }
static char *AppI(char *d, long v)
{
    char t[12];
    int  n = 0;
    if (v < 0) { *d++ = '-'; v = -v; }
    if (v == 0) t[n++] = '0';
    while (v > 0) { t[n++] = (char)('0' + (int)(v % 10)); v /= 10; }
    while (n > 0) *d++ = t[--n];
    *d = 0; return d;
}

/* CP865 (order-file / BBS wire encoding) -> CP1252 (GUI) for display.
   This is the CORRECT approach on Win 1.01, not a workaround: stock LISTBOX
   and dialog controls always draw in the ANSI System font and can't be
   switched to the CP865 OEM (Terminal) font -- WM_SETFONT and owner-draw
   listboxes are 2.0+ and absent here (the MSDOS Executive shows OEM filenames
   only by hand-painting with the OEM font).  KERNEL OemToAnsi is a fixed
   CP437->CP1252 table (0x9B->cent, 0x9D->yen), wrong for oe/OE -- CP865
   differs from CP437 exactly at 0x9B (oe) and 0x9D (OE).  So convert
   explicitly here.  See docs/win101-oem-encoding.md. */
static unsigned char cp865tab[128] = {
    0xC7, 0xFC, 0xE9, 0xE2, 0xE4, 0xE0, 0xE5, 0xE7, 0xEA, 0xEB, 0xE8, 0xEF, 0xEE, 0xEC, 0xC4, 0xC5,
    0xC9, 0xE6, 0xC6, 0xF4, 0xF6, 0xF2, 0xFB, 0xF9, 0xFF, 0xD6, 0xDC, 0xF8, 0xA3, 0xD8, 0x3F, 0x83,
    0xE1, 0xED, 0xF3, 0xFA, 0xF1, 0xD1, 0xAA, 0xBA, 0xBF, 0x3F, 0xAC, 0xBD, 0xBC, 0xA1, 0xAB, 0xA4,
    0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F,
    0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F,
    0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F,
    0x3F, 0xDF, 0x3F, 0x3F, 0x3F, 0x3F, 0xB5, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F, 0x3F,
    0x3F, 0xB1, 0x3F, 0x3F, 0x3F, 0x3F, 0xF7, 0x3F, 0xB0, 0x3F, 0xB7, 0x3F, 0x3F, 0xB2, 0x3F, 0xA0
};
static void OemAnsi(LPSTR src, LPSTR dst)
{
    unsigned char c;
    while ((c = (unsigned char)*src++) != 0)
        *dst++ = (char)((c < 0x80) ? c : cp865tab[c - 0x80]);
    *dst = 0;
}

/* (Re)populate the main-window list with not-yet-closed orders (NY/ACCEPTERET).
   Order text on disk is CP865; convert names to CP1252 (OemToAnsi) for the GUI. */
static void FillOrderList(void)
{
    static ORDER o;                 /* static: ~1KB struct, keep off the stack */
    char row[80], navn[40], *q;
    int  i;

    if (!hOrderList) return;
    SendMessage(hOrderList, LB_RESETCONTENT, 0, 0L);
    g_nList = 0;
    for (i = 0; OrderGetByIndex(i, &o); i++) {
        if (strcmp(o.status, "AFVIST") == 0 || strcmp(o.status, "LEVERET") == 0)
            continue;   /* hide closed; show NY/AFVENTER/ACCEPTERET/ACCEPTFEJL */
        if (g_nList >= MAXLIST) break;
        OemAnsi((LPSTR)o.navn, (LPSTR)navn);
        q = row;
        q = AppS(q, o.id);  q = AppS(q, "  ");
        q = AppS(q, navn);  q = AppS(q, "  ");
        q = AppS(q, o.status);
        SendMessage(hOrderList, LB_ADDSTRING, 0, (LONG)(LPSTR)row);
        strcpy(g_ids[g_nList], o.id);
        g_nList++;
    }
    SendMessage(hOrderList, LB_SETCURSEL, 0, 0L);   /* default-select first row */
}

/* Open the accept/reject detail dialog for the selected list row. */
static void OpenSelectedOrder(HWND hWnd)
{
    FARPROC lpProc;
    int     sel;

    sel = (int)SendMessage(hOrderList, LB_GETCURSEL, 0, 0L);
    if (sel < 0 || sel >= g_nList) return;
    strcpy(g_selId, g_ids[sel]);
    lpProc = MakeProcInstance(OrderDlgProc, hInst);
    if (DialogBox(hInst, "OrderBox", hWnd, lpProc) != IDCANCEL)
        FillOrderList();            /* status changed -> refresh */
    FreeProcInstance(lpProc);
    SetFocus(hOrderList);           /* return keyboard focus to the list */
}

int PASCAL WinMain(HANDLE hInstance, HANDLE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
{
    MSG msg;

    if (!hPrevInstance)
        if (!InitApplication(hInstance))
            return (FALSE);

    if (!InitInstance(hInstance, nCmdShow))
        return (FALSE);

    /* GetMessage blocks when idle, so we do not spin the cooperative
       scheduler.  A periodic timer (set in InitInstance) turns the loop
       over even with no user input, and we service the line after every
       dispatched message so message traffic cannot starve it. */
    while (GetMessage(&msg, NULL, NULL, NULL))
    {
        if (!TranslateAccelerator(hMainWnd, hAccel, &msg))
        {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        PollComm();
    }
    return (msg.wParam);
}

BOOL InitApplication(HANDLE hInstance)
{
    WNDCLASS wc;

    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = MainWndProc;
    wc.cbClsExtra = 0;
    wc.cbWndExtra = 0;
    wc.hInstance = hInstance;
    wc.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = GetStockObject(WHITE_BRUSH);
    wc.lpszMenuName = "VindMenu";
    wc.lpszClassName = "VindWClass";

    return (RegisterClass(&wc));
}

BOOL InitInstance(HANDLE hInstance, int nCmdShow)
{
    HWND hWnd;

    hInst = hInstance;

    hWnd = CreateWindow(
        "VindWClass",
        "Vindåsen",                 /* window title (Danish) */
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
        NULL, NULL, hInstance, NULL);

    if (!hWnd)
        return (FALSE);

    hMainWnd = hWnd;
    hAccel = LoadAccelerators(hInstance, (LPSTR)"VindAcc");

    /* Bring up the BBS line (COM2) and begin polling it via the timer.
       A session is greeted when carrier rises (see PollComm), or on the
       first received byte as a fallback. */
    CommOpen();
    BbsReset();
    LinkOpen();
    SetTimer(hWnd, ID_COMMTIMER, COMMTIMER_MS, NULL);

    ShowWindow(hWnd, nCmdShow);
    UpdateWindow(hWnd);
    return (TRUE);
}

long FAR PASCAL MainWndProc(HWND hWnd, unsigned message, WORD wParam, LONG lParam)
{
    FARPROC     lpProcAbout;
    PAINTSTRUCT ps;
    HDC         hDC;
    static char szBanner[]     = "Vindåsen - ordrestyring for dåsevin";
    static char szLineOpen[]   = "Linje COM2: åben (venter på opkald)";
    static char szLineClosed[] = "Linje COM2: lukket";

    switch (message)
    {
        case WM_COMMAND:
            switch (wParam)
            {
                case IDM_ABOUT:
                    lpProcAbout = MakeProcInstance(About, hInst);
                    DialogBox(hInst, "AboutBox", hWnd, lpProcAbout);
                    FreeProcInstance(lpProcAbout);
                    break;

                case IDM_EXIT:
                    DestroyWindow(hWnd);
                    break;

                case IDM_REFRESH:
                    FillOrderList();
                    break;

                case IDM_OPEN:
                    OpenSelectedOrder(hWnd);
                    break;

                case IDC_ORDERLIST:
                    if (HIWORD(lParam) == LBN_DBLCLK)
                        OpenSelectedOrder(hWnd);
                    break;

                default:
                    return (DefWindowProc(hWnd, message, wParam, lParam));
            }
            break;

        case WM_CREATE:
        {
            RECT rc;
            hOrderList = CreateWindow((LPSTR)"listbox", (LPSTR)NULL,
                WS_CHILD | WS_VISIBLE | WS_VSCROLL | WS_BORDER | LBS_NOTIFY,
                0, LIST_TOP, 0, 0,
                hWnd, (HMENU)IDC_ORDERLIST, hInst, (LPSTR)NULL);
            GetClientRect(hWnd, &rc);
            if (hOrderList)
                MoveWindow(hOrderList, 0, LIST_TOP, rc.right, rc.bottom - LIST_TOP, TRUE);
            FillOrderList();
            SetFocus(hOrderList);
            OrderOnChange(FillOrderList);   /* refresh when a BBS order arrives */
            break;
        }

        case WM_SIZE:
            if (hOrderList)
            {
                int cw = LOWORD(lParam);
                int ch = HIWORD(lParam) - LIST_TOP;
                if (ch < 0) ch = 0;
                MoveWindow(hOrderList, 0, LIST_TOP, cw, ch, TRUE);
            }
            break;

        case WM_TIMER:
            if (wParam == ID_COMMTIMER)
                PollComm();
            break;

        case WM_PAINT:
            hDC = BeginPaint(hWnd, &ps);
            TextOut(hDC, 10, 10, (LPSTR)szBanner, sizeof(szBanner) - 1);
            if (CommIsOpen())
                TextOut(hDC, 10, 30, (LPSTR)szLineOpen, sizeof(szLineOpen) - 1);
            else
                TextOut(hDC, 10, 30, (LPSTR)szLineClosed, sizeof(szLineClosed) - 1);
            EndPaint(hWnd, &ps);
            break;

        case WM_DESTROY:
            KillTimer(hWnd, ID_COMMTIMER);
            CommClose();
            LinkClose();
            PostQuitMessage(0);
            break;

        default:
            return (DefWindowProc(hWnd, message, wParam, lParam));
    }
    return (NULL);
}

BOOL FAR PASCAL About(HWND hDlg, unsigned message, WORD wParam, LONG lParam)
{
    switch (message)
    {
        case WM_INITDIALOG:
            return (TRUE);

        case WM_COMMAND:
            if (wParam == IDOK || wParam == IDCANCEL)
            {
                EndDialog(hDlg, TRUE);
                return (TRUE);
            }
            break;
    }
    return (FALSE);
}

BOOL FAR PASCAL OrderDlgProc(HWND hDlg, unsigned message, WORD wParam, LONG lParam)
{
    static ORDER o;                 /* static: ~1KB struct, keep off the stack */
    char b[96], nm[40], *q;
    int  i;

    switch (message)
    {
        case WM_INITDIALOG:
            if (OrderFind(g_selId, &o))
            {
                SetDlgItemText(hDlg, IDC_ID,      (LPSTR)o.id);
                SetDlgItemText(hDlg, IDC_STATUS,  (LPSTR)o.status);
                SetDlgItemText(hDlg, IDC_CREATED, (LPSTR)o.created);
                OemAnsi((LPSTR)o.navn,    (LPSTR)nm); SetDlgItemText(hDlg, IDC_NAVN,    (LPSTR)nm);
                OemAnsi((LPSTR)o.adresse, (LPSTR)nm); SetDlgItemText(hDlg, IDC_ADRESSE, (LPSTR)nm);
                OemAnsi((LPSTR)o.postby,  (LPSTR)nm); SetDlgItemText(hDlg, IDC_POSTBY,  (LPSTR)nm);
                for (i = 0; i < o.nItems; i++)
                {
                    OemAnsi((LPSTR)o.items[i].navn, (LPSTR)nm);
                    q = b;
                    q = AppI(q, (long)o.items[i].antal); q = AppS(q, " x ");
                    q = AppS(q, nm);                     q = AppS(q, " = ");
                    q = AppI(q, (long)o.items[i].pris * o.items[i].antal);
                    q = AppS(q, " kr.");
                    SendDlgItemMessage(hDlg, IDC_ITEMS, LB_ADDSTRING, 0, (LONG)(LPSTR)b);
                }
                q = b; q = AppI(q, o.total); q = AppS(q, " kr.");
                SetDlgItemText(hDlg, IDC_TOTAL, (LPSTR)b);
            }
            return (TRUE);

        case WM_COMMAND:
            switch (wParam)
            {
                case IDOK:            /* Win 1.01 Enter -> IDOK (default button) */
                case IDD_ACCEPT:
                    LinkAccept(g_selId);   /* send on COM3; AFVENTER until ack/timeout */
                    EndDialog(hDlg, IDD_ACCEPT);
                    return (TRUE);
                case IDD_REJECT:
                    OrderSetStatus(g_selId, (char *)"AFVIST");
                    EndDialog(hDlg, IDD_REJECT);
                    return (TRUE);
                case IDCANCEL:
                    EndDialog(hDlg, IDCANCEL);
                    return (TRUE);
            }
            break;
    }
    return (FALSE);
}
