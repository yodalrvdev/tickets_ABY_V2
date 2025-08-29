
# App Tickets — Import automatique + réimport admin (Render sans Shell)

## Local
```bash
pip install -r requirements.txt
python app.py
```
À l’ouverture, la base est créée et importée depuis `./data/Tickets.xlsx` si vide.

## Render
- Build: `pip install -r requirements.txt`
- Start: `gunicorn 'app:app' --bind 0.0.0.0:8080`
- Variables: `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DATABASE_URL`, `EXCEL_PATH=./data/Tickets.xlsx`
- **Pas de Shell** requis.

## Réimport admin
Allez dans **Paramètres** → section **Réimporter depuis l’Excel** :
- **Remise à zéro + import** : vide la base puis réimporte.
- **Incrémental (ajout)** : tente d’ajouter sans supprimer l’existant.
```
