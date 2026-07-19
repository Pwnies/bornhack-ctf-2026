/****************************************************************************

    COMM.C - serial line handling for the VINDAASEN ordering BBS.

    This module exposes a NON-BLOCKING CommRead() that the caller polls
	from the message loop and a timer.
    The driver fills the receive queue (sized at OpenComm time) from
    serial interrupts in the background; we drain it on each poll.

****************************************************************************/

#include <windows.h>
#include "comm.h"

static short idCom = -1;        /* OpenComm handle; -1 == closed */

BOOL CommOpen(void)
{
    DCB dcb;

    if (idCom >= 0)
        return (TRUE);                      /* already open */

    idCom = OpenComm((LPSTR)COMM_PORT, COMM_INQUEUE, COMM_OUTQUEUE);
    if (idCom < 0)
        return (FALSE);

    /* Fill the DCB from a MODE-style string, then attach our device id. */
    if (BuildCommDCB((LPSTR)COMM_SETTINGS, &dcb) < 0)
    {
        CloseComm(idCom);
        idCom = -1;
        return (FALSE);
    }
    dcb.Id = (BYTE)idCom;

    if (SetCommState(&dcb) < 0)
    {
        CloseComm(idCom);
        idCom = -1;
        return (FALSE);
    }

    /* Arm carrier-detect (RLSD/DCD) change events.  Windows 1.x has no call
       to read the current modem-status level, only these change events. */
    SetCommEventMask(idCom, EV_RLSD);
    return (TRUE);
}

void CommClose(void)
{
    if (idCom >= 0)
    {
        CloseComm(idCom);
        idCom = -1;
    }
}

BOOL CommIsOpen(void)
{
    return (idCom >= 0);
}

/* Non-blocking read of up to cbMax waiting bytes.  Returns the count placed
   in buf (0 if none), or a negative value if a comm error was latched. */
int CommRead(LPSTR buf, int cbMax)
{
    COMSTAT cs;
    short   err;
    int     n;

    if (idCom < 0)
        return (0);

    /* GetCommError clears the error latch and reports the queue depth. */
    err = GetCommError(idCom, &cs);

    if (cs.cbInQue == 0)
        return (err ? -1 : 0);

    n = (int)cs.cbInQue;
    if (n > cbMax)
        n = cbMax;

    n = ReadComm(idCom, buf, n);
    if (n < 0)                              /* error mid-read: count is negated */
        n = -n;
    return (n);
}

/* TRUE if the carrier-detect line changed state since the last call (a caller
   connecting or hanging up).  GetCommEventMask reports and clears the event.
   We treat any transition as a session boundary rather than tracking the
   level, since the level itself is not readable through the 1.x API. */
BOOL CommCarrierChanged(void)
{
    if (idCom < 0)
        return (FALSE);
    return ((GetCommEventMask(idCom, EV_RLSD) & EV_RLSD) ? TRUE : FALSE);
}

/* Queue bytes for transmission.  Returns bytes accepted, or <0 on error. */
int CommSend(LPSTR buf, int cb)
{
    if (idCom < 0)
        return (-1);
    return (WriteComm(idCom, buf, cb));
}
