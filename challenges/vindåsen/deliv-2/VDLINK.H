/****************************************************************************

    VDLINK.H - shared constants + id marshalling for the VDLOVV/VDLEV pair.

    The two fulfilment apps talk to each other with Windows messages
    (PostMessage).  Custom message ids sit at WM_USER+100.. to stay clear of
    control notifications (LB_* live at WM_USER+n).

    NB: Passing the order id: atoms are NOT shared between apps, and an
	11-digit id does not fit a 32-bit LPARAM.  But PostMessage delivers
	wParam/lParam intact across apps, so the id (always YYYYMMDD + a
	>=3-digit daily sequence, from ORDER.C OrderMakeId) travels split: the
	8-digit date in lParam, the sequence in wParam, rebuilt with VdlIdStr on
	the far side.

****************************************************************************/

#define WM_VDL_ORDER     (WM_USER + 100)   /* VDLOVV -> VDLEV : wParam=seq lParam=date */
#define WM_VDL_ACK       (WM_USER + 101)   /* VDLEV -> VDLOVV : wParam=seq lParam=date */
#define WM_VDL_DELIVERED (WM_USER + 102)   /* VDLEV -> VDLOVV : wParam=seq lParam=date */

#define VDLOVV_CLASS  "VdlovvClass"        /* monitor window class */
#define VDLEV_CLASS   "VdlevClass"         /* service window class */

/* rebuild the id string from its two message halves: 8-digit date + >=3-digit seq */
static void VdlIdStr(char *out, long date, WORD seq)
{
    char t[16], *q = out;
    long d;
    unsigned s;
    int n, i;

    n = 0; d = date; if (d == 0) t[n++] = '0';
    while (d > 0) { t[n++] = (char)('0' + (int)(d % 10)); d /= 10; }
    for (i = n; i < 8; i++) *q++ = '0';
    while (n > 0) *q++ = t[--n];

    n = 0; s = seq; if (s == 0) t[n++] = '0';
    while (s > 0) { t[n++] = (char)('0' + (int)(s % 10)); s /= 10; }
    for (i = n; i < 3; i++) *q++ = '0';
    while (n > 0) *q++ = t[--n];

    *q = 0;
}
