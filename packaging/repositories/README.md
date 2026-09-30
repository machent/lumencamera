# Signed APT and DNF repositories

Hosting: `https://machent.github.io/lumencamera/` through GitHub Pages.

The repository workflow downloads stable GitHub release packages, verifies their
SHA-256 checksums, signs RPM copies and repository metadata, tests installation
on Ubuntu 24.04 and Fedora 44, and deploys the complete site only after those
tests pass. Original release assets are preserved. Previous stable package
versions remain available. The APT suite is `stable`, independent of Ubuntu
codename, and contains architecture-independent packages with amd64/arm64
indices. DNF uses a shared noarch repository, without a Fedora-version path.

## One-time owner setup

1. Generate a dedicated signing key on your own computer with GnuPG installed:

   ```bash
   bash packaging/repositories/create-signing-key.sh
   ```

   This creates `~/lumencamera-signing/private-key.asc`, `public-key.asc`, and
   `fingerprint.txt`. Back up that directory privately. The signing key is
   unencrypted for unattended CI signing; keep its file private and store its
   contents only in the protected Actions secret. Never commit the private key.

2. At <https://github.com/machent/lumencamera/settings/secrets/actions>, create a
   repository secret named `LUMENCAMERA_SIGNING_KEY`. Paste the complete contents
   of `private-key.asc`, including both armor header and footer, into its value.

3. At <https://github.com/machent/lumencamera/settings/pages>, select **GitHub
   Actions** as the publishing source. Keep the default project URL.

4. Open the **Build signed APT and DNF repositories** workflow in Actions and
   select **Run workflow** on `main`. Wait for both the build and deployment to
   pass before advertising the installation commands.

5. Verify that the public `signing-key-fingerprint.txt` matches your local
   fingerprint file. Keep the same signing key for subsequent updates.

Without the signing secret, the workflow generates a disposable key and tests
the complete signed repositories but skips deployment. Its validation artifact
is for inspection and is not the public package repository.

## Updates

Publish stable `.deb` and `.noarch.rpm` release assets with a `SHA256SUMS` file
that covers those assets. Releases published manually trigger repository
refreshes. When another GitHub workflow publishes a release with `GITHUB_TOKEN`,
GitHub suppresses the follow-up release event; run this workflow manually after
that release. Editing repository scripts on `main` also triggers a refresh.

Users receive future versions through `sudo apt upgrade` or `sudo dnf upgrade`.
Existing users who installed 1.0 from a package file can add the repositories
without reinstalling the app.

## Installation and removal

The published landing page contains setup commands for both distributions.
Fedora enables package and repository-metadata signature verification; APT
restricts trust to `/etc/apt/keyrings/lumencamera.asc` through `Signed-By`.

Remove the DNF repository by deleting
`/etc/yum.repos.d/lumencamera.repo`. Remove the APT repository by deleting
`/etc/apt/sources.list.d/lumencamera.sources` and running `sudo apt update`.
The installed app remains until removed with the distribution's package manager.
