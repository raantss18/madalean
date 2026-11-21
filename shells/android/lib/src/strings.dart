/// User-facing texts: French by default, English switch.
library;

enum Lang { fr, en }

class S {
  const S(this.lang);
  final Lang lang;

  String _t(String fr, String en) => lang == Lang.fr ? fr : en;

  String get appTitle => 'Madalean';
  String get connectTitle =>
      _t('Connectez-vous à votre Madalean', 'Connect to your Madalean');
  String get connectIntro => _t(
    'Votre ordinateur Madalean fait tout le travail ; ce téléphone '
        's’y connecte par votre réseau Tailscale.',
    'Your Madalean computer does all the work; this phone connects to it '
        'through your Tailscale network.',
  );
  String get savedServers => _t('Serveurs enregistrés', 'Saved servers');
  String get open => _t('Ouvrir', 'Open');
  String get forget => _t('Oublier', 'Forget');
  String forgetConfirm(String host) => _t(
    'Oublier $host ? Il faudra appairer cet appareil à nouveau.',
    'Forget $host? This device will have to be paired again.',
  );
  String get cancel => _t('Annuler', 'Cancel');
  String get newServer => _t('Nouveau serveur', 'New server');
  String get addressLabel => _t('Adresse du serveur', 'Server address');
  String get addressHint => 'madalean.tailnet.ts.net';
  String get addressHelp => _t(
    'Adresse Tailscale complète (ex. madalean.votre-tailnet.ts.net), '
        'ou collez un lien madalean://pair',
    'Full Tailscale address (e.g. madalean.your-tailnet.ts.net), '
        'or paste a madalean://pair link',
  );
  String get pasteLink => _t('Coller un lien', 'Paste link');
  String get noLinkInClipboard => _t(
    'Le presse-papiers ne contient pas de lien madalean://pair.',
    'The clipboard holds no madalean://pair link.',
  );
  String get codeLabel => _t('Code d’appairage', 'Pairing code');
  String get codeHelp => _t(
    'Les 6 chiffres affichés sur l’ordinateur hôte '
        '(Réglages → Appareils).',
    'The 6 digits shown on the host computer (Settings → Devices).',
  );
  String get deviceLabel => _t('Nom de cet appareil', 'Name of this device');
  String get pair => _t('Appairer et ouvrir', 'Pair and open');
  String get connecting => _t('Connexion…', 'Connecting…');
  String get scanQr => _t('Scanner le QR code', 'Scan the QR code');
  String get scanIntro => _t(
    'Sur l’ordinateur : Réglages › Appareils › « Ajouter un appareil ». '
        'Puis scannez le QR code affiché.',
    'On the computer: Settings › Devices › “Add a device”. Then scan the '
        'QR code shown.',
  );
  String get orManual =>
      _t('Ou saisir l’adresse et le code', 'Or enter the address and code');
  String get scanAim => _t(
    'Visez le QR code affiché sur l’ordinateur.',
    'Point at the QR code shown on the computer.',
  );
  String get notMadaleanQr => _t(
    'Ce QR code n’est pas un code Madalean.',
    'This QR code is not a Madalean code.',
  );
  String get cameraWhyTitle => _t('Appareil photo', 'Camera');
  String get cameraWhy => _t(
    'Madalean utilise l’appareil photo seulement pour lire le QR code de '
        'l’ordinateur. Aucune image n’est enregistrée ni envoyée.',
    'Madalean uses the camera only to read the computer’s QR code. No '
        'image is saved or sent.',
  );
  String get continueLabel => _t('Continuer', 'Continue');
  String get cameraDenied => _t(
    'L’appareil photo n’est pas autorisé. Autorisez-le dans les réglages, '
        'ou saisissez l’adresse et le code à la main.',
    'The camera is not allowed. Allow it in the settings, or enter the '
        'address and code by hand.',
  );
  String get cameraError =>
      _t('Impossible d’utiliser l’appareil photo.', 'Cannot use the camera.');
  String get openSettings => _t('Ouvrir les réglages', 'Open settings');
  String get torch => _t('Lampe', 'Torch');
  String get language => _t('Langue', 'Language');

  // Errors.
  String get errEmpty => _t('Indiquez une adresse.', 'Enter an address.');
  String get errInvalid => _t('Adresse invalide.', 'Invalid address.');
  String get errCleartext => _t(
    'Seules les adresses https:// sont autorisées.',
    'Only https:// addresses are allowed.',
  );
  String get errFullName => _t(
    'Utilisez le nom complet, par ex. mon-pc.tailnet.ts.net '
        '(le certificat HTTPS est émis pour ce nom).',
    'Use the full name, e.g. my-pc.tailnet.ts.net '
        '(the HTTPS certificate is issued for that name).',
  );
  String get errCode =>
      _t('Le code comporte 6 chiffres.', 'The code has 6 digits.');
  String get errBadCode => _t(
    'Code incorrect ou expiré. Affichez un nouveau code sur l’hôte.',
    'Wrong or expired code. Show a new code on the host.',
  );
  String errLocked(int? s) => _t(
    'Trop d’essais : appairage bloqué'
        '${s != null ? ' encore ${(s / 60).ceil()} min' : ''}.',
    'Too many attempts: pairing locked'
        '${s != null ? ' for ${(s / 60).ceil()} more min' : ''}.',
  );
  String get errNotMadalean => _t(
    'Cette adresse répond, mais ce n’est pas un serveur Madalean.',
    'This address answers, but it is not a Madalean server.',
  );
  String get errProtocol => _t(
    'Réponse inattendue du serveur.',
    'Unexpected answer from the server.',
  );
  String get revoked => _t(
    'Cet appareil n’est plus autorisé (appairage révoqué sur l’hôte). '
        'Appairez-le à nouveau.',
    'This device is no longer authorised (pairing revoked on the host). '
        'Pair it again.',
  );

  // Network errors (why the server could not be reached).
  String get errTailscale => _t(
    'Tailscale n’est pas connecté sur ce téléphone. Ouvrez l’app '
        'Tailscale et activez-la, puis réessayez.',
    'Tailscale is not connected on this phone. Open the Tailscale app and '
        'turn it on, then try again.',
  );
  String get openTailscale => _t('Ouvrir Tailscale', 'Open Tailscale');
  String get errLookup => _t(
    'Adresse introuvable. Vérifiez l’adresse et la connexion du téléphone.',
    'Address not found. Check the address and the phone’s connection.',
  );
  String get errRefused => _t(
    'L’ordinateur refuse la connexion. Vérifiez que Madalean est lancé.',
    'The computer refuses the connection. Check that Madalean is running.',
  );
  String get errTimeout => _t(
    'Pas de réponse de l’ordinateur. Vérifiez qu’il est allumé et '
        'connecté.',
    'No answer from the computer. Check that it is on and connected.',
  );
  String get errNoNetwork => _t(
    'Ce téléphone n’a pas de réseau. Activez le Wi-Fi ou les données.',
    'This phone has no network. Turn on Wi-Fi or mobile data.',
  );
  String get errTls => _t(
    'Connexion sécurisée impossible (certificat refusé).',
    'Secure connection failed (certificate refused).',
  );

  // Unreachable screen.
  String get unreachableTitle =>
      _t('Serveur injoignable', 'Server unreachable');
  String unreachableBody(String host) => _t(
    'Impossible de joindre $host. Vérifiez que l’ordinateur hôte est allumé, '
        'que Madalean tourne et que Tailscale est connecté sur les deux '
        'appareils.',
    'Cannot reach $host. Check that the host computer is on, Madalean is '
        'running and Tailscale is connected on both devices.',
  );
  String get retry => _t('Réessayer', 'Retry');
  String get changeServer => _t('Changer de serveur', 'Change server');
  String details(String d) => _t('Détails : $d', 'Details: $d');

  // Web screen.
  String get exitTitle => _t('Quitter Madalean ?', 'Quit Madalean?');
  String get quit => _t('Quitter', 'Quit');
  String downloaded(String name) => _t(
    'Enregistré dans Téléchargements : $name',
    'Saved to Downloads: $name',
  );
  String get downloadFailed =>
      _t('Échec du téléchargement.', 'Download failed.');
  String get downloading => _t('Téléchargement…', 'Downloading…');

  // Updates.
  String get settings => _t('Réglages', 'Settings');
  String get autoUpdates =>
      _t('Mises à jour automatiques', 'Automatic updates');
  String get autoUpdatesHelp => _t(
    'Vérifie au plus deux fois par jour, télécharge et contrôle la '
        'signature ; l’installation demande toujours votre confirmation.',
    'Checks at most twice a day, downloads and verifies the signature; '
        'installing always asks for your confirmation.',
  );
  String get checkNow => _t('Vérifier maintenant', 'Check now');
  String get checking => _t('Vérification…', 'Checking…');
  String upToDate(String v) =>
      _t('Madalean $v est à jour.', 'Madalean $v is up to date.');
  String downloadingUpdate(String v, int pct) => _t(
    'Téléchargement de la version $v… $pct %',
    'Downloading version $v… $pct%',
  );
  String updateReady(String v) => _t('Mise à jour $v prête', 'Update $v ready');
  String updateRequired(String v) => _t(
    'Mise à jour $v nécessaire pour continuer à fonctionner avec l’hôte',
    'Update $v required to keep working with the host',
  );
  String get install => _t('Installer', 'Install');
  String get later => _t('Plus tard', 'Later');
  String get allowInstall => _t(
    'Autorisez « Madalean » à installer des applis (écran qui vient de '
        's’ouvrir), puis touchez à nouveau « Installer ».',
    'Allow “Madalean” to install apps (the screen that just opened), then '
        'tap “Install” again.',
  );
  String updateError(String kind) => switch (kind) {
    'tooOld' => _t(
      'Cette version est trop ancienne pour la mise à jour automatique : '
          'installez la nouvelle APK depuis la page de téléchargement.',
      'This version is too old to update automatically: install the new '
          'APK from the download page.',
    ),
    'network' => _t(
      'Mise à jour : canal injoignable (réseau).',
      'Update: channel unreachable (network).',
    ),
    'unsigned' => _t(
      'Mise à jour refusée : manifeste non signé.',
      'Update refused: unsigned manifest.',
    ),
    'badSignature' => _t(
      'Mise à jour refusée : signature invalide.',
      'Update refused: invalid signature.',
    ),
    'wrongChannel' => _t(
      'Mise à jour refusée : manifeste d’un autre canal.',
      'Update refused: manifest of another channel.',
    ),
    'badManifest' => _t(
      'Mise à jour refusée : manifeste illisible.',
      'Update refused: unreadable manifest.',
    ),
    'noFile' => _t(
      'Aucun APK pour cet appareil dans la mise à jour.',
      'No APK for this device in the update.',
    ),
    'checksum' => _t(
      'Mise à jour refusée : empreinte SHA-256 ou taille incorrecte.',
      'Update refused: wrong SHA-256 checksum or size.',
    ),
    'certificate' => _t(
      'Mise à jour refusée : l’APK n’est pas signé par le même certificat '
          'que l’appli installée.',
      'Update refused: the APK is not signed with the same certificate as '
          'the installed app.',
    ),
    'notConfigured' => _t(
      'Mises à jour non disponibles dans cette version de l’appli.',
      'Updates are not available in this build.',
    ),
    _ => _t(
      'Impossible de lancer l’installation.',
      'Could not start the installation.',
    ),
  };
}
