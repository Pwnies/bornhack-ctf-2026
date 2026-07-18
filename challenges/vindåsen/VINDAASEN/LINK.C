/****************************************************************************

    LINK.C - COM3 fulfilment link: direct polled UART I/O + line protocol.

    Windows 1.01's comm driver only knows COM1/COM2 (verified by disassembly,
    docs/win101-com3-support.md) and there is no pluggable comm-driver layer
    (docs/win101-com3-driver.md).  So we bypass the Windows COMM API and talk
    to the COM3 8250/16550 UART directly with inp/outp (from SLIBC.LIB -- they
    link clean, no NEIERR).  Polled, interrupts OFF (IER=0, MCR OUT2=0), so the
    COM1/COM3 shared-IRQ4 conflict never arises; "data ready?" comes purely
    from LSR.  Serviced from the same message-loop + WM_TIMER drain as COM2,
    never blocking.  1200-8N1 with the 16550 FIFO on, so <=12 bytes arrive
    between 100ms polls (inside the 16-byte FIFO).  See docs/win101-com3-bypass.md.

    Protocol (line-oriented plain text, CRLF out / LF-or-CRLF in; Danish
    keywords; order fields are the raw CP865 bytes as stored):
      out on accept:   ORDRE|<id>|<navn>|<adresse>|<postby>|<items>|<total>
      in ack:          KVITTER <id>     -> order acknowledged (ACCEPTERET)
      in delivery:     LEVERET <id>     -> order delivered (LEVERET)
    On accept the order goes AFVENTER and a 5s deadline is armed; the ack
    clears it (ACCEPTERET), a timeout faults it (ACCEPTFEJL).  A LEVERET may
    arrive any time, even while another order awaits its ack.

****************************************************************************/

#include <windows.h>            /* GetCurrentTime (DWORD ms) */
#include <conio.h>              /* inp / outp (port I/O) */
#include <string.h>
#include "link.h"
#include "order.h"

#define P3_BASE  0x3E8          /* COM3 */
#define P3_RBR   (P3_BASE+0)    /* RX / (DLL when DLAB=1) */
#define P3_THR   (P3_BASE+0)    /* TX (same address as RBR) */
#define P3_IER   (P3_BASE+1)    /* (DLM when DLAB=1) */
#define P3_FCR   (P3_BASE+2)
#define P3_LCR   (P3_BASE+3)
#define P3_MCR   (P3_BASE+4)
#define P3_LSR   (P3_BASE+5)

#define LSR_DR   0x01           /* data ready */
#define LSR_THRE 0x20           /* transmit-hold empty */

#define ACK_MS   5000UL         /* accept-ack deadline */
#define NPEND    8              /* concurrent orders awaiting ack */

/* ---- small formatting helpers ------------------------------------------ */

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

/* ---- raw UART (polled, interrupts off) --------------------------------- */

static unsigned char txbuf[256];        /* software TX ring */
static int txhead = 0, txtail = 0;

#define TX_STUCK_MS 2000UL              /* give up on a byte if THR won't free (dead line) */

static void Com3Init(void)              /* 1200-8N1, polled, FIFO on */
{
    outp(P3_IER, 0x00);                 /* mask all UART interrupts */
    outp(P3_LCR, 0x80);                 /* DLAB=1 -> divisor latch */
    outp(P3_BASE+0, 0x60);              /* DLL = 96 -> 1200 baud */
    outp(P3_BASE+1, 0x00);              /* DLM = 0 */
    outp(P3_LCR, 0x03);                 /* DLAB=0, 8 data / no parity / 1 stop */
    outp(P3_FCR, 0xC7);                 /* enable + clear FIFO, 14-byte trigger */
    outp(P3_MCR, 0x03);                 /* DTR+RTS; OUT2=0 (interrupt line gated) */
    (void)inp(P3_RBR);                  /* clear stale RX byte */
    (void)inp(P3_LSR);                  /* clear latched line-status bits */
    txhead = txtail = 0;
}

static int Com3Read(unsigned char *buf, int max)    /* non-blocking */
{
    int n = 0;
    while (n < max && (inp(P3_LSR) & LSR_DR))
        buf[n++] = (unsigned char)inp(P3_RBR);
    return n;
}

/* Push queued TX bytes into the UART, ONE byte per THRE assertion.  We do NOT
   write a 16-byte "FIFO burst" on THRE: dosbox-x's 16550 emulation sets THRE
   when the transmit register can take a byte, not when 16 slots are free, so a
   16-byte burst silently drops whatever doesn't fit -- that lost ~749 bytes out
   of a 4.6KB firmware push even when paced slowly, and truncated it (EOT lost)
   when pushed fast.  One-byte-per-THRE hits the full 1200-baud line rate anyway
   (the line moves ~120 B/s regardless of FIFO depth).

   wait==0: opportunistic -- send only what fits right now, never spin (used by
            LinkPoll so the message loop stays responsive).
   wait!=0: keep going until the ring is empty, bounded-spinning for THR to free
            (used by Com3Send so a queued byte is never dropped).  GetCurrentTime
            advances on the hardware tick independent of the Windows scheduler,
            so the timeout works even while we spin. */
static void Com3Pump(int wait)
{
    DWORD end;
    while (txtail != txhead) {
        if (inp(P3_LSR) & LSR_THRE) {
            outp(P3_THR, txbuf[txtail]);
            txtail = (txtail + 1) & 255;
            continue;
        }
        if (!wait) return;              /* THR busy and not waiting: try next poll */
        end = GetCurrentTime() + TX_STUCK_MS;
        while (!(inp(P3_LSR) & LSR_THRE))
            if ((long)(GetCurrentTime() - end) >= 0) return;   /* line dead: keep rest queued */
    }
}

/* Enqueue every byte and transmit it -- blocking, never dropping.  The ring is
   fully drained before returning, so COM3 sends synchronously; when the caller
   forwards faster than 1200 baud (a firmware push), this applies real
   backpressure (it stops reading COM2 while it blocks) instead of overflowing a
   fixed ring and discarding bytes. */
static void Com3Send(char *buf, int cb)
{
    int i, nxt;
    for (i = 0; i < cb; i++) {
        nxt = (txhead + 1) & 255;
        if (nxt == txtail) {            /* ring full: drain to make room */
            Com3Pump(1);
            nxt = (txhead + 1) & 255;
            if (nxt == txtail) return;  /* still full after the stuck-line timeout: give up */
        }
        txbuf[txhead] = (unsigned char)buf[i];
        txhead = nxt;
    }
    Com3Pump(1);
}

/* ---- public raw senders (used by BBS.C to forward a firmware upload) ----- */

void LinkSendRaw(char *buf, int cb)     /* queue arbitrary bytes, no framing */
{
    Com3Send(buf, cb);
}

void LinkSendLine(char *s)              /* queue a line + CRLF (keyword frame) */
{
    Com3Send(s, (int)strlen(s));
    Com3Send("\r\n", 2);
}

/* ---- pending-ack table ------------------------------------------------- */

static struct { char id[16]; DWORD start; } pend[NPEND];
static int npend = 0;

static void PendAdd(char *id)           /* add or refresh a deadline */
{
    int i;
    for (i = 0; i < npend; i++)
        if (strcmp(pend[i].id, id) == 0) { pend[i].start = GetCurrentTime(); return; }
    if (npend < NPEND) {
        strcpy(pend[npend].id, id);
        pend[npend].start = GetCurrentTime();
        npend++;
    }
}

static void PendRemove(char *id)
{
    int i;
    for (i = 0; i < npend; i++)
        if (strcmp(pend[i].id, id) == 0) { pend[i] = pend[--npend]; return; }
}

/* ---- inbound line dispatch --------------------------------------------- */

static char linebuf[128];
static int  linelen = 0;

static void DispatchLine(char *s)
{
    char kw[12], id[16];
    int  i = 0, j = 0;

    while (s[i] && s[i] != ' ' && j < 11) kw[j++] = s[i++];
    kw[j] = 0;
    while (s[i] == ' ') i++;
    j = 0; while (s[i] && j < 15) id[j++] = s[i++];
    id[j] = 0;

    if (strcmp(kw, "KVITTER") == 0) {          /* accept acknowledged */
        PendRemove(id);
        OrderSetStatus(id, "ACCEPTERET");
    } else if (strcmp(kw, "LEVERET") == 0) {   /* delivery notification */
        PendRemove(id);
        OrderSetStatus(id, "LEVERET");
    }
    /* unknown keyword: ignore */
}

static void LineByte(unsigned char c)
{
    if (c == '\n') { linebuf[linelen] = 0; if (linelen) DispatchLine(linebuf); linelen = 0; }
    else if (c == '\r') { /* ignore */ }
    else if (linelen < (int)sizeof(linebuf) - 1) linebuf[linelen++] = (char)c;
    /* overflow: drop until newline */
}

/* ---- public raw byte receiver (used by BBS.C response-read phase) ------ */

int LinkReadByte(char *c)               /* non-blocking; 1 if a byte was read */
{
    return Com3Read((unsigned char *)c, 1) == 1;
}

/* ---- public entry points ----------------------------------------------- */

void LinkOpen(void)
{
    Com3Init();
    linelen = 0;
    npend = 0;
}

void LinkClose(void)
{
}

/* Send the order description over COM3, mark it AFVENTER, arm the 5s wait. */
void LinkAccept(char *id)
{
    static ORDER o;                     /* ~1KB: keep off the stack */
    char line[400], *q;
    int  i;

    if (!OrderFind(id, &o)) return;

    q = line;
    q = AppS(q, "ORDRE|");
    q = AppS(q, o.id);       *q++ = '|';
    q = AppS(q, o.navn);     *q++ = '|';
    q = AppS(q, o.adresse);  *q++ = '|';
    q = AppS(q, o.postby);   *q++ = '|';
    for (i = 0; i < o.nItems; i++) {
        if (i) *q++ = ';';
        q = AppS(q, o.items[i].artikel);
        *q++ = '*';
        q = AppI(q, (long)o.items[i].antal);
    }
    *q++ = '|';
    q = AppI(q, o.total);
    *q++ = '\r'; *q++ = '\n';

    Com3Send(line, (int)(q - line));
    OrderSetStatus(id, "AFVENTER");
    PendAdd(id);
}

/* Drain COM3, dispatch complete lines, and fault any order past its ack
   deadline.  Called from the message-loop / WM_TIMER drain (never blocks). */
void LinkPoll(void)
{
    unsigned char b[64];
    int   n, i;
    DWORD now;

    Com3Pump(0);                        /* opportunistic: never blocks the loop */
    n = Com3Read(b, sizeof(b));
    for (i = 0; i < n; i++)
        LineByte(b[i]);

    now = GetCurrentTime();
    for (i = 0; i < npend; ) {
        if ((DWORD)(now - pend[i].start) >= ACK_MS) {
            char id[16];
            strcpy(id, pend[i].id);
            pend[i] = pend[--npend];            /* remove before the callback */
            OrderSetStatus(id, "ACCEPTFEJL");
        } else {
            i++;
        }
    }
}
