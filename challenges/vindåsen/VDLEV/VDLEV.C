/****************************************************************************

    VDLEV.C - VinDaasen Leverance (dummy fulfilment SERVICE).

    Runs on the fulfilment Windows 1.01 machine alongside the monitor VDLOVV.
    Receives orders from VDLOVV via Windows messages (order id split across
    wParam=seq / lParam=date -- see VDLINK.H), acknowledges each IMMEDIATELY,
    and marks it delivered after a pseudo-random 10 s .. 5 min.  Shows the
    pending orders with a live countdown.  Talks only to VDLOVV, never the
    serial line.  See docs/win101-ipc.md.  ASCII source.

****************************************************************************/

#include <windows.h>
#include <stdlib.h>             /* rand, srand */
#include "vdlink.h"

HANDLE hInst;

static HWND hList = NULL;
#define IDC_LIST  100
#define ID_TIMER  1
#define TIMER_MS  1000          /* countdown / delivery check, 1 s */
#define NPEND     32

#define DELAY_MIN 10            /* seconds */
#define DELAY_MAX 300           /* seconds (5 min) */

static struct { long date; WORD seq; DWORD deadline; } pend[NPEND];
static int npend = 0;

long FAR PASCAL MainWndProc(HWND, unsigned, WORD, LONG);

static char *AppS(char *d, char *s) { while (*s) *d++ = *s++; *d = 0; return d; }
static char *AppI(char *d, long v)
{
    char t[12]; int n = 0;
    if (v < 0) { *d++ = '-'; v = -v; }
    if (v == 0) t[n++] = '0';
    while (v > 0) { t[n++] = (char)('0' + (int)(v % 10)); v /= 10; }
    while (n > 0) *d++ = t[--n];
    *d = 0; return d;
}

static HWND FindMon(void) { return FindWindow((LPSTR)VDLOVV_CLASS, (LPSTR)NULL); }

/* redraw the pending list: "<id>   <remaining>s" per order */
static void Refresh(void)
{
    DWORD now = GetCurrentTime();
    char  line[40], id[16], *q;
    long  rem;
    int   i;

    if (!hList) return;
    SendMessage(hList, LB_RESETCONTENT, 0, 0L);
    for (i = 0; i < npend; i++) {
        rem = (long)(pend[i].deadline - now) / 1000L;
        if (rem < 0) rem = 0;
        VdlIdStr(id, pend[i].date, pend[i].seq);
        q = line;
        q = AppS(q, id);
        q = AppS(q, "   ");
        q = AppI(q, rem);
        q = AppS(q, "s");
        SendMessage(hList, LB_ADDSTRING, 0, (LONG)(LPSTR)line);
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
        wc.lpszClassName = (LPSTR)VDLEV_CLASS;
        if (!RegisterClass(&wc)) return (FALSE);
    }
    hInst = hInstance;
    srand((unsigned)GetCurrentTime());

    hWnd = CreateWindow((LPSTR)VDLEV_CLASS, (LPSTR)"VinDaasen Leverance",
        WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
        NULL, NULL, hInstance, NULL);
    if (!hWnd) return (FALSE);

    SetTimer(hWnd, ID_TIMER, TIMER_MS, NULL);
    ShowWindow(hWnd, SW_SHOWNORMAL);    /* force visible even when load=' d iconic */
    UpdateWindow(hWnd);

    while (GetMessage(&msg, NULL, NULL, NULL)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
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
            hList = CreateWindow((LPSTR)"listbox", (LPSTR)NULL,
                WS_CHILD | WS_VISIBLE | WS_VSCROLL | WS_BORDER,
                0, 0, rc.right, rc.bottom, hWnd, (HMENU)IDC_LIST, hInst, (LPSTR)NULL);
            break;
        }
        case WM_SIZE:
            if (hList) MoveWindow(hList, 0, 0, LOWORD(lParam), HIWORD(lParam), TRUE);
            break;

        case WM_VDL_ORDER:                  /* new order from VDLOVV (wParam=seq lParam=date) */
        {
            HWND hMon;
            int  delay;
            if (npend < NPEND) {
                delay = DELAY_MIN + rand() % (DELAY_MAX - DELAY_MIN + 1);   /* 10..MAX s */
                pend[npend].date     = lParam;
                pend[npend].seq      = wParam;
                pend[npend].deadline = GetCurrentTime() + (DWORD)delay * 1000UL;
                npend++;
            }
            hMon = FindMon();               /* ack immediately */
            if (hMon) PostMessage(hMon, WM_VDL_ACK, wParam, lParam);
            Refresh();
            break;
        }

        case WM_TIMER:
        {
            DWORD now = GetCurrentTime();
            HWND  hMon = FindMon();
            int   i;
            for (i = 0; i < npend; ) {
                if ((long)(now - pend[i].deadline) >= 0) {     /* due */
                    if (hMon) PostMessage(hMon, WM_VDL_DELIVERED,
                                          pend[i].seq, pend[i].date);
                    pend[i] = pend[--npend];
                } else {
                    i++;
                }
            }
            Refresh();
            break;
        }

        case WM_DESTROY:
            KillTimer(hWnd, ID_TIMER);
            PostQuitMessage(0);
            break;

        default:
            return (DefWindowProc(hWnd, message, wParam, lParam));
    }
    return (0L);
}
