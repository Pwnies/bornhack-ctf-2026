/****************************************************************************

    BBS.H - stub ordering-session handler (BBS.C).

****************************************************************************/

void BbsReset(void);                    /* end/clear the current session */
void BbsConnect(void);                  /* new caller: reset + greet immediately */
void BbsReceive(LPSTR buf, int cb);     /* handle bytes arriving on the line */
