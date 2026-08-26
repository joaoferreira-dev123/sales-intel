"""Testes que rodam sem internet."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import db, main
from app.extractor import HeuristicExtractor, LLMExtractor, escolher_extrator
from app.fetcher import extrair_texto

HTML = """
<html><head><title>Acme Tecnologia | Solucoes</title></head>
<body><nav>menu</nav><script>x=1</script>
<p>A Acme Tecnologia desenvolve plataformas de automacao industrial para
industrias de medio porte, com foco em reducao de custo operacional.</p>
<p>Fundada em 2015, atende mais de 200 clientes em todo o Brasil e mantem
operacao propria de suporte tecnico especializado.</p>
<footer>contato@acme.com.br (11) 98888-7777</footer></body></html>
"""

def test_extrair_texto_remove_script_e_pega_titulo():
    titulo, texto = extrair_texto(HTML)
    assert titulo == "Acme Tecnologia | Solucoes"
    assert "x=1" not in texto
    assert "automacao industrial" in texto

def test_heuristico_monta_briefing():
    titulo, texto = extrair_texto(HTML)
    b = HeuristicExtractor().extrair("https://acme.com.br", titulo, texto)
    assert b.empresa == "Acme Tecnologia"
    assert "automacao" in b.resumo
    assert b.confianca == "baixa"

def test_heuristico_encontra_contatos():
    titulo, texto = extrair_texto(HTML)
    b = HeuristicExtractor().extrair("https://acme.com.br", titulo, texto)
    assert "contato@acme.com.br" in b.contatos

def test_escolher_extrator_sem_chave_devolve_heuristico(monkeypatch):
    # Trava L-05: sem chave de API no ambiente, o sistema roda no heuristico.
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert isinstance(escolher_extrator(), HeuristicExtractor)

def test_escolher_extrator_com_chave_devolve_llm(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "chave-de-teste-sem-valor")
    assert isinstance(escolher_extrator(), LLMExtractor)

def test_extrator_que_falha_nao_derruba_a_requisicao(monkeypatch):
    class ExtratorQuebrado:
        nome = "llm"

        def extrair(self, url, titulo, texto):
            raise RuntimeError("provedor fora do ar")

    monkeypatch.setattr(main, "escolher_extrator", lambda: ExtratorQuebrado())
    monkeypatch.setattr(main, "buscar_html", lambda url: HTML)
    monkeypatch.setattr(db, "salvar", lambda *args, **kwargs: datetime.now(timezone.utc))
    monkeypatch.setattr(db, "buscar", lambda *args, **kwargs: None)

    # Sem "with": nao dispara o lifespan, entao nao chama db.criar_tabelas()
    # nem cria o arquivo briefings.db.
    client = TestClient(main.app)
    resp = client.post(
        "/api/briefings",
        json={"urls": ["https://acme.com.br"], "forcar_atualizacao": True},
    )

    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 1
    item = dados[0]
    assert item["extrator"] == "heuristico"
    assert item["briefing"]["confianca"] == "baixa"
    assert item["origem"] == "novo"

