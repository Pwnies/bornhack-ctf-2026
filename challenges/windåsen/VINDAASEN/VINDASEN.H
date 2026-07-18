/****************************************************************************

    VINDASEN.H - resource IDs and function prototypes.

    Code and identifiers are in English; user-facing strings live in the
    .RC / .C files and are Danish (Windows ANSI / CP1252 encoding).

****************************************************************************/

/* Menu / command IDs */
#define IDM_ABOUT   100
#define IDM_EXIT    101
#define IDM_REFRESH 102         /* Bestillinger -> Opdater (refresh list) */
#define IDM_OPEN    103         /* Bestillinger -> Aabn valgte (open selected) */

/* Main-window order list (child control) */
#define IDC_ORDERLIST 200

/* Order-detail dialog (OrderBox) control IDs */
#define IDC_ITEMS   201         /* listbox of order lines */
#define IDC_ID      210
#define IDC_STATUS  211
#define IDC_CREATED 212
#define IDC_NAVN    213
#define IDC_ADRESSE 214
#define IDC_POSTBY  215
#define IDC_TOTAL   216
#define IDD_ACCEPT  220         /* "Accepter" button */
#define IDD_REJECT  221         /* "Afvis" button */

/* Timer that heartbeats the serial-line poll (see WinMain comment) */
#define ID_COMMTIMER 1
#define COMMTIMER_MS 100

/* Function prototypes */
int  PASCAL WinMain(HANDLE, HANDLE, LPSTR, int);
BOOL InitApplication(HANDLE);
BOOL InitInstance(HANDLE, int);
long FAR PASCAL MainWndProc(HWND, unsigned, WORD, LONG);
BOOL FAR PASCAL About(HWND, unsigned, WORD, LONG);
BOOL FAR PASCAL OrderDlgProc(HWND, unsigned, WORD, LONG);
