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
  String get addressHint => 'nom-du-pc.tailnet.ts.net';
  String get addressHelp => _t(
    'Nom Tailscale complet (port 10500 par défaut), '
        'ou collez un lien madalean://pair',
    'Full Tailscale name (port 10500 by default), '
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
  String get scanHint => _t(
    'Astuce : scannez le QR code de l’hôte avec l’appareil photo, '
        'il ouvre cette appli directement.',
    'Tip: scan the host’s QR code with the camera app, '
        'it opens this app directly.',
  );
  String get languageSwitch => _t('English', 'Français');

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
}
