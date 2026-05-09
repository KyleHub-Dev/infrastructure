# Git Forge Decision Note

Status: on ice.

I created this Forgejo stack as a possible canonical `git.kylehub.dev` home, but it should not be deployed for now.

The main concern is operational coupling: if the homelab or infra has to move, the primary source forge would move with it. That makes the Git host a bottleneck for recovering or rebuilding the rest of the infrastructure. GitHub does not have that problem for this setup because the repositories can be cloned from outside the homelab regardless of local infra state.

Current direction:

- Keep GitHub as the practical primary home for repos that are tied to infrastructure recovery, private work, or broad ecosystem expectations.
- Use Codeberg for new FOSS projects where the project is truly public/free software and the community/non-profit forge alignment matters.
- Do not self-host Forgejo as the canonical source of truth unless there is a stronger reason than dissatisfaction with GitHub's UX or ownership.

If this stack is revisited later, solve these first:

- Offsite backups and tested restores.
- A bootstrap path that does not depend on the Forgejo instance itself.
- Clear rules for which repos are canonical here versus mirrored elsewhere.
- External SSH/HTTPS access that works during partial infra failure.

For now, Codeberg for new FOSS plus GitHub for continuity is the simpler and lower-risk path.
