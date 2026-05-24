
import re

def test_regex(content):
    ap_patterns = [
        r"(?:Apertura|Abri[oó]|Disponible desde|Desde el):\s*([^.]{10,100}?\d{2}:\d{2})",
        r"Este cuestionario no estar[aá] disponible hasta el\s*([^.]{10,100}?\d{2}:\d{2})"
    ]
    
    apertura = "N/A"
    for p_in in ap_patterns:
        match = re.search(p_in, content, re.IGNORECASE)
        if match:
            apertura = match.group(1).strip()
            break
    return apertura

# Test cases
test_cases = [
    "Apertura: lunes, 11 de mayo de 2026, 09:00",
    "Abrió: lunes, 11 de mayo de 2026, 09:00",
    "Abre: lunes, 11 de mayo de 2026, 09:00",
    "Abierto: lunes, 11 de mayo de 2026, 09:00",
    "Disponible desde: lunes, 11 de mayo de 2026, 09:00",
    "Desde el: lunes, 11 de mayo de 2026, 09:00",
    "Este cuestionario no estará disponible hasta el lunes, 11 de mayo de 2026, 09:00",
    "Abierto lunes, 11 de mayo de 2026, 09:00", # No colon
]

for tc in test_cases:
    print(f"Input: {tc}")
    print(f"Result: {test_regex(tc)}")
    print("-" * 20)
