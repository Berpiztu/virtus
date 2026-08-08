# Reglas para Claude en este repositorio

Estas reglas son permanentes y se aplican en todas las sesiones:

1. **Sin atribución en los commits.** Nunca añadas líneas de coautoría ni pies
   de atribución a los mensajes de commit, PRs o cualquier artefacto del repo
   (nada de `Co-Authored-By`, enlaces de sesión, "Generated with...", etc.).
   El mensaje de commit describe solo el cambio. Claude NUNCA debe aparecer
   como autor ni committer: configura siempre la identidad git como
   `iosub <iosub@gabiges.com>` antes de hacer commit.

2. **El usuario prueba antes de commit y push.** Después de hacer cambios en la
   app (`labs/agentic-misalignment`), arranca el servidor
   (`python app.py --host 0.0.0.0`) y espera a que el usuario confirme que
   funciona. No hagas `git commit` ni `git push` hasta que el usuario dé el OK.
