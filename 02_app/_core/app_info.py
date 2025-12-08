INFO_TEXT_MODAL = """Mit dieser App kannst du **vertieft über eigene Dokumentsammlungen recherchieren**.

Die App dient zum Testen. **Beachte, dass Sprachmodelle (LLMs) Fehler machen und die Ergebnisse fehlerhaft oder unvollständig sein können.** Überprüfe die Ergebnisse immer.

Deine Fragen werden an Clouddienste weitergeleitet und dort verarbeitet. **Gib daher nur als öffentlich klassifizierte Informationen als Fragen ein!** Beachte auch, dass die Nutzung anonymisiert aufgezeichnet wird und Mitarbeitende vom Statistischen Amt Eingaben stichprobenartig überprüfen, um die App zu verbessern.

Zu Demonstrationszwecken bezieht die App für die Antworten eine kleine Auswahl von [Kantonsratsprotokollen des Kantons Zürich ein](https://opendata.swiss/de/dataset/zurcher-kantonsratsprotokolle-des-19-jahrhunderts). 

Verantwortlich: Statistisches Amt, [Team Data](mailto:datashop@statistik.zh.ch).

App-Version v0.3. Letzte Aktualisierung 08.12.2025

### Wie funktioniert die App?

Die App arbeitet in mehreren Schritten:

1. **Suchanfragen formulieren**: Basierend auf deiner Fragestellung generiert die App gezielte Suchanfragen.  
2. **Recherche durchführen**: Anschließend durchsucht die App die Dokumente nach passenden Textstellen.  
3. **Relevanz prüfen**: Die gefundenen Passagen werden daraufhin geprüft, ob sie für deine Fragestellung von Bedeutung sind.  
4. **Ganze Beschlüsse analysieren**: Zu relevanten Textstellen werden die Dokumente im Volltext analysiert und inhaltlich in Bezug auf die Frage zusammengefasst.  
5. **Recherchestand reflektieren**: Falls die iterative Recherche aktiviert ist, bewertet die App den bisherigen Erkenntnisstand und entscheidet, ob weitere Recherchen notwendig sind.  
6. **Abschlussbericht erstellen**: Die App fasst die Ergebnisse in einem Abschlussbericht zusammen.
""".strip()

INFO_TEXT_SIDEBAR = """
Recherchewerkzeug für eigene Dokumentsammlungen.\n\n:red[Achtung: Dies ist ein experimenteller Prototyp. Gib nur als öffentlich klassifizierte Daten als Fragen ein. Die Ergebnisse können fehlerhaft oder unvollständig sein. **Überprüfe die Ergebnisse immer.**] \n\n Die Bearbeitung kann einige Minuten dauern, abhängig von der Komplexität der Anfrage und der Anzahl der relevanten Dokumente.
""".strip()

SAMPLE_QUERY = "Was hat der Kantonsrat zu Steuern entschieden?"