// Le Déniveleur — page web.
// Envoie la demande à l'API, suit le calcul, affiche les propositions sur la carte.
"use strict";

const FOND_IGN =
  "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0" +
  "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM" +
  "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/png";
const CLE_REGLAGES = "deniveleur-reglages";

const $ = (id) => document.getElementById(id);
const etat = {
  infos: null,
  depart: null, // [longitude, latitude]
  propositions: [],
  choisie: 0,
  marqueurDepart: null,
  marqueurProfil: null,
  marqueursMontees: [],
  suivi: null,
};

// ---------------------------------------------------------------- utilitaires

function lireStockage() {
  try { return JSON.parse(localStorage.getItem(CLE_REGLAGES) || "{}"); } catch { return {}; }
}
function ecrireStockage(valeurs) {
  try { localStorage.setItem(CLE_REGLAGES, JSON.stringify(valeurs)); } catch { /* navigation privée */ }
}
function km(m) { return (m / 1000).toFixed(1).replace(".", ","); }
function allureEnSecondes(texte) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(texte.trim());
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}
function afficherMessage(texte) {
  const bloc = $("message");
  bloc.textContent = texte || "";
  bloc.hidden = !texte;
}
function couleurPente(pente) {
  const paliers = etat.infos.paliers_pente, couleurs = etat.infos.couleurs_pente;
  let i = 0;
  while (i < paliers.length && pente >= paliers[i]) i++;
  return couleurs[i];
}
function echapper(texte) {
  const div = document.createElement("div");
  div.textContent = texte;
  return div.innerHTML;
}

// ---------------------------------------------------------------------- carte

const carte = new maplibregl.Map({
  container: "carte",
  style: {
    version: 8,
    sources: {
      ign: { type: "raster", tiles: [FOND_IGN], tileSize: 256, maxzoom: 18,
             attribution: "© IGN · © contributeurs OpenStreetMap" },
    },
    layers: [{ id: "ign", type: "raster", source: "ign" }],
  },
  center: [2.2215, 48.8428],
  zoom: 12.5,
  attributionControl: { compact: true },
});
carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

function placerDepart(longitude, latitude, texte) {
  etat.depart = [longitude, latitude];
  if (!etat.marqueurDepart) {
    const pastille = document.createElement("div");
    pastille.style.cssText =
      "width:22px;height:22px;border-radius:50%;background:#e8622c;border:3px solid #fff;" +
      "box-shadow:0 1px 5px rgba(0,0,0,.45)";
    etat.marqueurDepart = new maplibregl.Marker({ element: pastille, draggable: true })
      .setLngLat(etat.depart).addTo(carte);
    etat.marqueurDepart.on("dragend", () => {
      const p = etat.marqueurDepart.getLngLat();
      placerDepart(p.lng, p.lat);
    });
  } else {
    etat.marqueurDepart.setLngLat(etat.depart);
  }
  $("depart-texte").textContent =
    texte || `${latitude.toFixed(4).replace(".", ",")} N, ${longitude.toFixed(4).replace(".", ",")} E`;
  $("aide-carte").hidden = true;
}

carte.on("click", (e) => placerDepart(e.lngLat.lng, e.lngLat.lat));

carte.on("load", () => {
  carte.addSource("trace", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  carte.addSource("autres", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  carte.addLayer({ id: "autres", type: "line", source: "autres",
    paint: { "line-color": "#3d4a43", "line-width": 3, "line-opacity": 0.35, "line-dasharray": [2, 1.5] } });
  carte.addLayer({ id: "trace-bord", type: "line", source: "trace",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#ffffff", "line-width": 8 } });
  carte.addLayer({ id: "trace", type: "line", source: "trace",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": ["get", "couleur"], "line-width": 4.5 } });
});

// -------------------------------------------------------------------- réglages

function synchroniserAffichage() {
  $("distance-valeur").textContent = `${$("distance").value} km`;
  $("dplus-valeur").textContent = `${$("dplus").value} m`;
  $("duree-valeur").textContent = `${String($("duree").value).replace(".", ",")} min`;
  $("rayon-valeur").textContent = `${String($("rayon").value).replace(".", ",")} km`;
  const cotes = choixCoche("mode") === "cotes";
  document.querySelectorAll(".mode-boucle").forEach((el) => { el.hidden = cotes; });
  document.querySelectorAll(".mode-cotes").forEach((el) => { el.hidden = !cotes; });
  $("generer").textContent = cotes ? "Trouver des côtes" : "Trouver mes boucles";
  const cible = choixCoche("objectif") === "cible";
  $("bloc-cible").hidden = !cible;
  $("note-boucle").textContent = choixCoche("boucle") === "allers-retours"
    ? "Un même chemin peut être repris, une fois dans chaque sens (culs-de-sac compris)."
    : "Jamais deux fois le même chemin, jamais de demi-tour.";
}
function choixCoche(nom) {
  return document.querySelector(`input[name=${nom}]:checked`).value;
}
function cocher(nom, valeur) {
  const radio = document.querySelector(`input[name=${nom}][value="${valeur}"]`);
  if (radio) radio.checked = true;
}
for (const id of ["distance", "dplus", "duree", "rayon"]) {
  $(id).addEventListener("input", synchroniserAffichage);
}
for (const radio of document.querySelectorAll("input[name=objectif], input[name=boucle], input[name=mode]")) {
  radio.addEventListener("change", synchroniserAffichage);
}

function lireFormulaire() {
  const cible = choixCoche("objectif") === "cible";
  return {
    mode: choixCoche("mode"),
    duree: Number($("duree").value),
    rayon: Number($("rayon").value),
    allureIntervalle: $("allure-intervalle").value,
    distance: Number($("distance").value),
    tolerance: Number($("tolerance").value),
    cible,
    dplus: Number($("dplus").value),
    voies: choixCoche("voies"),
    escaliers: choixCoche("escaliers"),
    boucle: choixCoche("boucle"),
    allure: $("allure").value,
    propositions: Number($("propositions").value),
    depart: etat.depart,
  };
}

function restaurerFormulaire() {
  const r = lireStockage();
  if (r.distance) $("distance").value = r.distance;
  if (r.tolerance) $("tolerance").value = String(r.tolerance);
  if (r.cible) document.querySelector("input[name=objectif][value=cible]").checked = true;
  if (r.dplus) $("dplus").value = r.dplus;
  if (r.mode) cocher("mode", r.mode);
  if (r.duree) $("duree").value = r.duree;
  if (r.rayon) $("rayon").value = r.rayon;
  if (r.allureIntervalle) $("allure-intervalle").value = r.allureIntervalle;
  if (r.voies) cocher("voies", r.voies);
  if (r.escaliers) cocher("escaliers", r.escaliers);
  if (r.boucle) cocher("boucle", r.boucle);
  if (r.allure) $("allure").value = r.allure;
  if (r.propositions) $("propositions").value = String(r.propositions);
  synchroniserAffichage();
  return r.depart;
}

$("ma-position").addEventListener("click", () => {
  if (!navigator.geolocation) { afficherMessage("Ce navigateur ne donne pas la position."); return; }
  $("ma-position").textContent = "…";
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      $("ma-position").textContent = "Ma position";
      placerDepart(pos.coords.longitude, pos.coords.latitude, "Ma position");
      carte.flyTo({ center: etat.depart, zoom: 14 });
    },
    () => {
      $("ma-position").textContent = "Ma position";
      afficherMessage("Position indisponible : autorise la localisation ou touche la carte.");
    },
    { enableHighAccuracy: true, timeout: 10000 },
  );
});

// ------------------------------------------------------------------- calcul

$("formulaire").addEventListener("submit", async (e) => {
  e.preventDefault();
  afficherMessage("");
  const f = lireFormulaire();
  if (!f.depart) { afficherMessage("Place d'abord le départ en touchant la carte."); return; }
  const cotes = f.mode === "cotes";
  const texteAllure = cotes ? f.allureIntervalle : f.allure;
  const allure = allureEnSecondes(texteAllure);
  if (texteAllure && allure === null) { afficherMessage("Allure à écrire sous la forme 6:00."); return; }
  ecrireStockage(f);

  const corps = {
    latitude: f.depart[1],
    longitude: f.depart[0],
    distance_km: f.distance,
    tolerance_pct: f.tolerance,
    dplus_cible: f.cible ? f.dplus : null,
    voies: f.voies,
    sans_escaliers: f.escaliers === "eviter",
    allers_retours: f.boucle === "allers-retours",
    propositions: f.propositions,
    allure_s_par_km: allure,
    type: f.mode,
    duree_intervalle_s: Math.round(f.duree * 60),
    rayon_cotes_km: f.rayon,
  };
  $("generer").disabled = true;
  $("progression").hidden = false;
  $("barre-remplie").style.width = "0";
  $("progression-texte").textContent = "Envoi de la demande…";
  try {
    const reponse = await fetch("/api/calculs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    });
    const donnees = await reponse.json();
    if (!reponse.ok) throw new Error(lireErreur(donnees));
    etat.modeCalcul = f.mode;
    suivre(donnees.id);
  } catch (erreur) {
    terminerAttente();
    afficherMessage(erreur.message || "Le serveur ne répond pas.");
  }
});

function lireErreur(donnees) {
  if (typeof donnees.detail === "string") return donnees.detail;
  if (Array.isArray(donnees.detail)) return "Réglage invalide : " + donnees.detail.map((d) => d.msg).join(", ");
  return "Erreur inattendue.";
}

function terminerAttente() {
  clearTimeout(etat.suivi);
  $("generer").disabled = false;
  $("progression").hidden = true;
}

async function suivre(id) {
  let donnees;
  try {
    const reponse = await fetch(`/api/calculs/${id}`);
    donnees = await reponse.json();
    if (!reponse.ok) throw new Error(lireErreur(donnees));
  } catch (erreur) {
    terminerAttente();
    afficherMessage(erreur.message || "Connexion perdue avec le serveur.");
    return;
  }
  if (donnees.etat === "en_attente") {
    $("progression-texte").textContent = donnees.position > 0
      ? `En file d'attente : ${donnees.position} recherche(s) avant la tienne…`
      : "Démarrage…";
  } else if (donnees.etat === "en_cours") {
    $("barre-remplie").style.width = `${Math.round(donnees.avancement * 100)}%`;
    const reste = Math.max(1, Math.round((1 - donnees.avancement) * (etat.infos.budget_s + 3)));
    $("progression-texte").textContent = etat.modeCalcul === "cotes"
      ? "Recherche des côtes…"
      : `Recherche des meilleures boucles… encore ${reste} s environ`;
  } else if (donnees.etat === "termine") {
    $("barre-remplie").style.width = "100%";
    terminerAttente();
    afficherResultats(id, donnees.resultat);
    return;
  } else {
    terminerAttente();
    afficherMessage(`Le calcul a échoué : ${donnees.erreur}`);
    return;
  }
  etat.suivi = setTimeout(() => suivre(id), 1000);
}

// ---------------------------------------------------------------- résultats

function afficherResultats(id, resultat) {
  etat.propositions = resultat.propositions.map((p) => ({ ...p, idCalcul: id }));
  if (!etat.propositions.length && resultat.type === "cotes") {
    $("resultats").hidden = true;
    afficherMessage("Aucune côte de cette durée trouvée. Essaie une autre durée, une allure " +
      "différente ou un bas de côte plus loin du départ.");
    return;
  }
  if (!etat.propositions.length) {
    $("resultats").hidden = true;
    afficherMessage("Aucune boucle trouvée avec ces réglages. Essaie une autre distance, " +
      "« Allers-retours acceptés », « Indifférent » pour les voies, ou un départ plus proche des chemins.");
    return;
  }
  const onglets = $("onglets");
  onglets.innerHTML = "";
  etat.propositions.forEach((p, i) => {
    const bouton = document.createElement("button");
    bouton.className = "onglet";
    bouton.type = "button";
    bouton.setAttribute("role", "tab");
    bouton.innerHTML = p.type === "cote"
      ? `<strong>${p.temps_texte}</strong>${p.distance_m} m · ${String(p.pente_moyenne_pct).replace(".", ",")} %`
      : `<strong>${p.dplus_m} m</strong>${km(p.distance_m)} km`;
    bouton.addEventListener("click", () => choisir(i));
    onglets.appendChild(bouton);
  });
  onglets.hidden = etat.propositions.length < 2;
  $("resultats").hidden = false;
  choisir(0);
  $("resultats").scrollIntoView({ behavior: "smooth", block: "start" });
  // La carte peut avoir changé de taille (affichage des résultats) : on la recale.
  setTimeout(() => carte.resize(), 300);
}

function segmentsColores(points) {
  // Regroupe les points par tronçons de même couleur de pente (mesurée sur ~60 m).
  const features = [];
  let courant = null;
  for (let i = 1; i < points.length; i++) {
    let j = i;
    while (j < points.length - 1 && points[j][3] - points[i - 1][3] < 60) j++;
    const d = points[j][3] - points[i - 1][3];
    const pente = d > 0 ? Math.abs(points[j][2] - points[i - 1][2]) / d * 100 : 0;
    const couleur = couleurPente(pente);
    if (!courant || courant.properties.couleur !== couleur) {
      courant = { type: "Feature", properties: { couleur },
                  geometry: { type: "LineString", coordinates: [[points[i - 1][0], points[i - 1][1]]] } };
      features.push(courant);
    }
    courant.geometry.coordinates.push([points[i][0], points[i][1]]);
  }
  return { type: "FeatureCollection", features };
}

function choisir(rang) {
  etat.choisie = rang;
  const p = etat.propositions[rang];
  document.querySelectorAll(".onglet").forEach((b, i) => b.setAttribute("aria-selected", String(i === rang)));

  const autres = etat.propositions.filter((_, i) => i !== rang).map((q) => ({
    type: "Feature", properties: {},
    geometry: { type: "LineString", coordinates: q.points.map((pt) => [pt[0], pt[1]]) },
  }));
  const dessiner = () => {
    carte.getSource("autres").setData({ type: "FeatureCollection", features: autres });
    carte.getSource("trace").setData(segmentsColores(p.points));
    // Une pastille numérotée au sommet de chaque côte.
    etat.marqueursMontees.forEach((m) => m.remove());
    etat.marqueursMontees = (p.type === "cote" ? [] : p.montees).map((m) => {
      const pastille = document.createElement("div");
      pastille.textContent = m.numero;
      pastille.title = `${m.nom} : +${m.denivele_m} m`;
      pastille.style.cssText =
        "min-width:20px;height:20px;padding:0 3px;border-radius:10px;background:#fff;" +
        "border:2px solid #e8622c;color:#e8622c;font:700 11px/16px system-ui,sans-serif;text-align:center";
      return new maplibregl.Marker({ element: pastille }).setLngLat(m.haut).addTo(carte);
    });
  };
  if (carte.isStyleLoaded()) dessiner(); else carte.once("load", dessiner);
  const bornes = new maplibregl.LngLatBounds();
  p.points.forEach((pt) => bornes.extend([pt[0], pt[1]]));
  carte.fitBounds(bornes, { padding: 40, duration: 600 });

  const fiche = $("fiche");
  if (p.type === "cote") {
    fiche.innerHTML = `
    <h3 class="nom-cote">${echapper(p.nom)}</h3>
    <div class="chiffres">
      <div class="chiffre"><b>${p.temps_texte}</b><span>par montée (estimé)</span></div>
      <div class="chiffre"><b>${p.distance_m} m</b><span>longueur</span></div>
      <div class="chiffre"><b>+${p.denivele_m} m</b><span>dénivelé</span></div>
      <div class="chiffre"><b>${String(p.pente_moyenne_pct).replace(".", ",")} %</b><span>pente moyenne</span></div>
      <div class="chiffre"><b>${String(p.pente_max_pct).replace(".", ",")} %</b><span>pente max</span></div>
      <div class="chiffre"><b>${km(p.approche_m)} km</b><span>depuis le départ</span></div>
    </div>
    <svg id="profil" class="profil" role="img" aria-label="Profil d'altitude"></svg>
    <p id="profil-info" class="profil-info">Glisse le doigt sur le profil pour suivre la carte</p>
    <a class="bouton-gpx" href="/api/calculs/${p.idCalcul}/gpx/${p.rang}" download>Télécharger la côte (GPX)</a>
    <p class="astuce">Monte à l'effort, redescends en récupération par le même chemin, et recommence.
      ${p.part_chemin_pct >= 50 ? "Côte surtout en sentier." : "Côte surtout sur bitume."}
      ${p.escaliers_m > 0 ? `Attention : ${p.escaliers_m} m d'escaliers.` : ""}</p>`;
    dessinerProfil(p);
    return;
  }
  fiche.innerHTML = `
    <div class="chiffres">
      <div class="chiffre"><b>${km(p.distance_m)} km</b><span>distance</span></div>
      <div class="chiffre"><b>${p.dplus_m} m</b><span>D+</span></div>
      <div class="chiffre"><b>${p.temps_texte}</b><span>temps estimé</span></div>
      <div class="chiffre"><b>${p.part_chemin_pct} %</b><span>sentier</span></div>
      <div class="chiffre"><b>${p.altitude_min_m}–${p.altitude_max_m}</b><span>altitude (m)</span></div>
      <div class="chiffre"><b>${p.montees.length}</b><span>côtes</span></div>
    </div>
    <svg id="profil" class="profil" role="img" aria-label="Profil d'altitude"></svg>
    <p id="profil-info" class="profil-info">Glisse le doigt sur le profil pour suivre la carte</p>
    <a class="bouton-gpx" href="/api/calculs/${p.idCalcul}/gpx/${p.rang}" download>Télécharger le GPX</a>
    <p class="astuce">Dans Strava (sur ordinateur) : « Créer un itinéraire », puis la petite flèche
      d'import en haut à gauche de la carte. Le fichier s'importe aussi dans Garmin Connect,
      Suunto et Coros.</p>
    ${p.alertes.length ? `<ul class="alertes">${p.alertes.map((a) => `<li>${echapper(a)}</li>`).join("")}</ul>` : ""}
    <div class="montees">
      <h3>Les côtes</h3>
      <ol>${p.montees.map((m) => `
        <li data-lng="${m.bas[0]}" data-lat="${m.bas[1]}">
          <span class="num">${m.numero}</span>
          <span class="nom">${echapper(m.nom)}</span>
          <span class="gain">+${m.denivele_m} m</span>
          <span class="detail">km ${km(m.debut_m)} · ${m.longueur_m} m · ${String(m.pente_moyenne_pct).replace(".", ",")} % de moyenne, ${String(m.pente_max_pct).replace(".", ",")} % max</span>
        </li>`).join("")}</ol>
    </div>`;
  fiche.querySelectorAll(".montees li").forEach((li) => {
    li.addEventListener("click", () => {
      carte.flyTo({ center: [Number(li.dataset.lng), Number(li.dataset.lat)], zoom: 15.5 });
      $("carte").scrollIntoView({ behavior: "smooth" });
    });
  });
  dessinerProfil(p);
}

function dessinerProfil(p) {
  const svg = $("profil");
  const largeur = svg.clientWidth || 360, hauteur = 150;
  const marge = { gauche: 34, droite: 6, haut: 8, bas: 20 };
  svg.setAttribute("viewBox", `0 0 ${largeur} ${hauteur}`);
  const pts = p.points;
  const dMax = pts[pts.length - 1][3];
  const zMin = Math.floor((p.altitude_min_m - 5) / 10) * 10;
  const zMax = Math.ceil((p.altitude_max_m + 5) / 10) * 10;
  const X = (d) => marge.gauche + (d / dMax) * (largeur - marge.gauche - marge.droite);
  const Y = (z) => hauteur - marge.bas - ((z - zMin) / (zMax - zMin)) * (hauteur - marge.haut - marge.bas);

  let html = "";
  // Graduations d'altitude et de distance.
  const pasZ = zMax - zMin > 150 ? 50 : 25;
  for (let z = Math.ceil(zMin / pasZ) * pasZ; z <= zMax; z += pasZ) {
    html += `<line x1="${marge.gauche}" x2="${largeur - marge.droite}" y1="${Y(z)}" y2="${Y(z)}" stroke="#ece8df"/>`;
    html += `<text x="${marge.gauche - 4}" y="${Y(z) + 3}" font-size="9" text-anchor="end" fill="#5c6560">${z}</text>`;
  }
  if (dMax < 3000) {
    // Côte courte : graduations en mètres.
    const pasM = dMax > 1200 ? 250 : 100;
    for (let m = 0; m <= dMax; m += pasM) {
      html += `<text x="${X(m)}" y="${hauteur - 6}" font-size="9" text-anchor="middle" fill="#5c6560">${m} m</text>`;
    }
  } else {
    const pasKm = dMax > 20000 ? 5 : dMax > 8000 ? 2 : 1;
    for (let k = 0; k * 1000 <= dMax; k += pasKm) {
      html += `<text x="${X(k * 1000)}" y="${hauteur - 6}" font-size="9" text-anchor="middle" fill="#5c6560">${k}</text>`;
    }
  }
  // Aire colorée par la pente.
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i];
    const pente = b[3] > a[3] ? Math.abs(b[2] - a[2]) / (b[3] - a[3]) * 100 : 0;
    html += `<polygon points="${X(a[3])},${Y(zMin)} ${X(a[3])},${Y(a[2])} ${X(b[3])},${Y(b[2])} ${X(b[3])},${Y(zMin)}" fill="${couleurPente(pente)}" opacity="0.85"/>`;
  }
  html += `<polyline fill="none" stroke="#1d211f" stroke-width="1" points="${pts.map((q) => `${X(q[3])},${Y(q[2])}`).join(" ")}"/>`;
  html += `<line id="profil-curseur" y1="${marge.haut}" y2="${hauteur - marge.bas}" stroke="#1f3b2d" stroke-width="1.5" visibility="hidden"/>`;
  svg.innerHTML = html;

  const curseur = svg.querySelector("#profil-curseur");
  const survol = (clientX) => {
    const r = svg.getBoundingClientRect();
    const x = (clientX - r.left) * (largeur / r.width);
    const d = Math.min(dMax, Math.max(0, ((x - marge.gauche) / (largeur - marge.gauche - marge.droite)) * dMax));
    let i = 0;
    while (i < pts.length - 1 && pts[i][3] < d) i++;
    const pt = pts[i];
    curseur.setAttribute("x1", X(pt[3]));
    curseur.setAttribute("x2", X(pt[3]));
    curseur.setAttribute("visibility", "visible");
    const position = dMax < 3000 ? `${Math.round(pt[3])} m` : `km ${km(pt[3])}`;
    $("profil-info").textContent = `${position} · ${Math.round(pt[2])} m d'altitude`;
    if (!etat.marqueurProfil) {
      const point = document.createElement("div");
      point.style.cssText = "width:14px;height:14px;border-radius:50%;background:#1f3b2d;border:2px solid #fff";
      etat.marqueurProfil = new maplibregl.Marker({ element: point });
    }
    etat.marqueurProfil.setLngLat([pt[0], pt[1]]).addTo(carte);
  };
  svg.addEventListener("pointermove", (e) => survol(e.clientX));
  svg.addEventListener("pointerdown", (e) => survol(e.clientX));
}

// -------------------------------------------------------------------- démarrage

async function demarrer() {
  try {
    etat.infos = await (await fetch("/api/infos")).json();
  } catch {
    afficherMessage("Le serveur ne répond pas. Réessaie dans un instant.");
    return;
  }
  $("zone").textContent = etat.infos.zone;
  const allure = etat.infos.allure_defaut_s_par_km;
  $("allure").value = `${Math.floor(allure / 60)}:${String(allure % 60).padStart(2, "0")}`;
  const [o, s, e, n] = etat.infos.emprise;
  carte.setMaxBounds([[o - 0.05, s - 0.03], [e + 0.05, n + 0.03]]);
  const departMemorise = restaurerFormulaire();
  if (departMemorise) {
    placerDepart(departMemorise[0], departMemorise[1]);
  } else {
    const [lat, lng] = etat.infos.depart_defaut;
    placerDepart(lng, lat, "Rue Dailly, Saint-Cloud");
  }
  // Légende des pentes.
  const legende = document.createElement("div");
  legende.className = "legende-pente";
  const bornes = [0, ...etat.infos.paliers_pente];
  legende.innerHTML = etat.infos.couleurs_pente.map((c, i) =>
    `<div><i style="background:${c}"></i>${i < bornes.length - 1 ? `${bornes[i]}–${bornes[i + 1]} %` : `> ${bornes[i]} %`}</div>`,
  ).join("");
  carte.addControl({ onAdd: () => legende, onRemove: () => legende.remove() }, "bottom-left");
}

demarrer();
