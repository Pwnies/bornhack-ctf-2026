/* ADMIN.H - forward declaration for the admin login function (ADMIN.C). */

#ifndef ADMIN_H
#define ADMIN_H

/* Returns 1 if the entered password is correct, 0 otherwise.
   Declared with lowercase `far` (not the FAR macro which expands to _far):
   QC25 -AS honours `far` and emits CALL FAR PTR at call sites + RETF in
   the body, even in small model -- which is required for the CTF exploit. */
int far StartAdminLogin(void);

#endif /* ADMIN_H */
