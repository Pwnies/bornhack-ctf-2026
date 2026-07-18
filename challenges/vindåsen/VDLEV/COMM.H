/****************************************************************************

    COMM.H - public interface of the serial line module (COMM.C).

    The BBS ordering line runs on COM2; COM1 is the serial mouse.

****************************************************************************/

#define COMM_PORT      "COM2"              /* BBS line */
#define COMM_SETTINGS  "COM2:1200,n,8,1"   /* 1200 baud, 8-N-1 (period-typical) */
#define COMM_INQUEUE   1024                /* receive queue (interrupt-buffered) */
#define COMM_OUTQUEUE  4096                /* transmit queue: must hold a full
                                              screen redraw; WriteComm drops
                                              bytes that don't fit, so too small
                                              a queue truncates ANSI screens */

BOOL CommOpen(void);                       /* TRUE on success */
void CommClose(void);
BOOL CommIsOpen(void);
BOOL CommCarrierChanged(void);             /* TRUE once per DCD/RLSD transition */
int  CommRead(LPSTR buf, int cbMax);       /* non-blocking: >=0 bytes, <0 error */
int  CommSend(LPSTR buf, int cb);          /* bytes queued, or <0 error */
