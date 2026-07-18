@ECHO OFF
REM ==========================================================================
REM  VINDASEN build - run from the VINDASEN drive (D:) in the WIN3.0 DOSBox.
REM
REM  Hybrid toolchain (see repo notes):
REM    1) QuickC (QCL) compiles the C against the QCWIN Windows headers
REM    2) the QCWIN linker links against the Windows 1.x libs in WINLIB.10
REM    3) the native Windows 1.0 RC compiles + binds the resources
REM    4) NEHDR stamps the NE expected-Windows-version down to 1.0
REM ==========================================================================
SET PATH_=%PATH%
SET INCLUDE_=%INCLUDE%
SET LIB_=%LIB%

REM --- 1) compile ---------------------------------------------------------
IF EXIST VINDèSEN.EXE DEL VINDèSEN.EXE
SET PATH=C:\QC25\BIN;C:\QCWIN\BIN
SET INCLUDE=C:\QCWIN\INCLUDE
qcl -c -AS -Gw -Zp -W3 VINDASEN.C COMM.C BBS.C ORDER.C LINK.C ADMIN.C

REM --- 2) link ------------------------------------------------------------
SET LIB=C:\WINLIB.10
link /NOD /A:16 VINDASEN+COMM+BBS+ORDER+LINK+ADMIN+CSUP,,,C51STUBS+LIBH+SLIBW+SWINLIBC+SLIBC,VINDASEN.DEF

REM --- 3) resources (native 1.0 RC; SDK101\BIN first so RC + its RCPP are
REM        the 1.0 tools, not WINDEV's 3.0 ones) -----------------------------
SET PATH=C:\SDK101\BIN;C:\QCWIN\BIN;C:\TOOLS
SET INCLUDE=C:\SDK101\INCLUDE
IF NOT EXIST VINDASEN.EXE GOTO LINKFAIL
RC VINDASEN.RC VINDASEN.EXE

REM --- 4) winver fixup + NEIERR guard -------------------------------------
REM  NEHDR stamps the expected-Windows version down to 1.0 AND fails (nonzero
REM  errorlevel) if the NE has the "errors in image" flag (NEIERR) set -- an
REM  image Windows 1.01 would reject with a misleading "Not enough memory to
REM  run".  On any NEHDR failure we DELETE the .EXE so a broken build is never
REM  run.  (NEHDR must run AFTER RC: RC binding can rewrite the header.)
IF NOT EXIST VINDASEN.EXE GOTO RCFAIL
NEHDR VINDASEN.EXE /WVER:1.0
IF ERRORLEVEL 1 GOTO NEFAIL
REN VINDASEN.EXE VINDèSEN.EXE
ECHO *** BUILD OK: VINDèSEN.EXE ***
GOTO DONE

:LINKFAIL
ECHO *** BUILD FAILED: link produced no VINDASEN.EXE ***
GOTO DONE
:RCFAIL
ECHO *** BUILD FAILED: RC removed or rejected VINDASEN.EXE ***
GOTO DONE
:NEFAIL
ECHO *** BUILD FAILED: NEHDR rejected the NE (NEIERR or header error) ***
IF EXIST VINDASEN.EXE DEL VINDASEN.EXE
GOTO DONE

:DONE
SET PATH=%PATH_%
SET INCLUDE=%INCLUDE_%
SET LIB=%LIB_%
