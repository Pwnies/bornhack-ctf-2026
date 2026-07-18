/****************************************************************************

    ADMIN.C - admin login gate with intentional stack-overflow vulnerability.

    Separated from BBS.C and declared with lowercase `far` (not the FAR macro
    which expands to _far in the QCWIN headers -- QC25 ignores _far in -AS but
    honours the bare `far` keyword).  QC25 -AS emits CALL FAR PTR at call sites
    in BBS.C and RETF at the end of the function body, which pushes/pops CS:IP
    (4 bytes) instead of just IP (2 bytes).  This makes the saved return CS:IP
    overwritable by an attacker who overflows pw[128].

****************************************************************************/

#include <windows.h>
#include "comm.h"
#include "order.h"
#include "admin.h"

/* ----- helpers ----------------------------------------------------------- */

static void adm_send(LPSTR s, int n)  { CommSend(s, n); }
#define ASEND(lit) adm_send((LPSTR)(lit), sizeof(lit)-1)

/* ----- StartAdminLogin --------------------------------------------------- */

int far StartAdminLogin(void)
{
    char pw[128];   /* stack-local; no bounds check -- intentionally vulnerable */
    char c;
    int  n;

    ASEND("\x1b[2J\x1b[H");           /* CLS */
    ASEND("  Administration\r\n");
    ASEND("  =============\r\n");
    ASEND("\r\n");
    ASEND("  Kodeord: ");

    n = 0;
    for (;;) {
        while (CommRead((LPSTR)&c, 1) <= 0) { }
        if (c == '\r' || c == '\n') { pw[n] = '\0'; ASEND("\r\n"); break; }
        if ((c == '\b' || c == 0x7f) && n > 0) { n--; ASEND("\b \b"); continue; }
        if ((unsigned char)c >= ' ') {
            pw[n++] = c;   /* missing bounds check -- the bug */
            { char m = '*'; CommSend((LPSTR)&m, 1); }
        }
    }

    if (OrderCheckAdmin(pw)) {
        return 1;
    }
    ASEND("\r\n  Forkert kodeord.\r\n");
    ASEND("\r\n  Tryk en tast for menu...");
    return 0;
}
