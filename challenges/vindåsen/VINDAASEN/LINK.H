/****************************************************************************

    LINK.H - COM3 fulfilment link (public interface of LINK.C).

    Windows 1.01's comm API supports only COM1/COM2 (COM1 = mouse, COM2 =
    BBS), so the COM3 machine link is driven by DIRECT polled UART I/O at
    0x3E8 -- no OpenComm.  See docs/win101-com3-*.md.  Line-oriented plain
    text; serviced from the same message-loop drain as COM2 (no blocking).

****************************************************************************/

void LinkOpen(void);            /* init the COM3 UART (1200-8N1, polled) */
void LinkClose(void);
void LinkPoll(void);            /* drain COM3, dispatch lines, check timeouts */
void LinkAccept(char *id);      /* send an order over COM3, arm the 5s ack wait */
void LinkSendRaw(char *buf, int cb); /* queue raw bytes on COM3 (no framing) */
void LinkSendLine(char *s);     /* queue a line on COM3 (appends CRLF) */
int  LinkReadByte(char *c);     /* non-blocking single-byte RX; 1 if got byte */
