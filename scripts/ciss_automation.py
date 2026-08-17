import os
import sys
import asyncio
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright


# --- CONFIGURATIONS ---
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR.parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

SCREENSHOT_DIR = BASE_DIR.parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

USERNAME = os.environ.get("CISSLIVE_USERNAME")
PASSWORD = os.environ.get("CISSLIVE_PASSWORD")
TARGET_FILE_NAME = "5358 - Controle de Lote.xls"
TARGET_PATH = DOWNLOAD_DIR / TARGET_FILE_NAME


print(f"\n==================================================")
print(f"🕒 Execução iniciada em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"==================================================")


def get_dates():
    """Calculate dates: 1 year ago and 2 years in the future."""
    today = datetime.now()
    start_date = (today - timedelta(days=365)).strftime("%d/%m/%Y")
    end_date = (today + timedelta(days=730)).strftime("%d/%m/%Y")
    return start_date, end_date


async def save_screenshot(page, name):
    try:
        path = SCREENSHOT_DIR / f"{name}.png"
        await page.screenshot(path=str(path), timeout=5000, animations="disabled")
        print(f"📸 Screenshot salvo: {path}")
    except Exception as e:
        print(f"⚠️ Não foi possível salvar screenshot '{name}': {e}")


async def run_automation():
    if not USERNAME or not PASSWORD:
        print("❌ ERRO: CISSLIVE_USERNAME ou CISSLIVE_PASSWORD não definidos!")
        print("Configure os Secrets no repositório GitHub.")
        sys.exit(1)

    start_date, end_date = get_dates()
    print(f"📅 Período de Validade: {start_date} até {end_date}")

    async with async_playwright() as p:
        print("🚀 Inicializando navegador...")
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            accept_downloads=True,
        )
        page = await context.new_page()

        try:
            # 1. Open Cisslive
            print("🌐 Acessando Cisslive...")
            await page.goto("https://kopquirinopolis.cisslive.com.br/#", timeout=90000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)
            await save_screenshot(page, "01_pagina_inicial")

            # 2. Login - Username
            print(f"👤 Preenchendo e-mail: {USERNAME}")
            await page.fill("#username", USERNAME)
            await save_screenshot(page, "02_email_preenchido")

            print("➡️ Clicando em Entrar...")
            await page.click("button:has-text('Entrar')")
            await page.wait_for_timeout(3000)
            await save_screenshot(page, "03_pos_email_submit")

            # Check if username error appeared
            error_el = await page.query_selector("div.text-red-600")
            if error_el:
                error_text = await error_el.inner_text()
                print(f"❌ Erro no login (Email inválido?): {error_text}")
                await browser.close()
                sys.exit(1)

            has_error_text = await page.locator("text=don't have an account").count() > 0
            if has_error_text:
                print("❌ Erro no login (Email não cadastrado)")
                await browser.close()
                sys.exit(1)

            # 3. Login - Password
            print("🔑 Aguardando campo de senha...")
            password_selector = "input[type='password']"
            await page.wait_for_selector(password_selector, timeout=10000)
            print("🔑 Preenchendo senha...")
            await page.fill(password_selector, PASSWORD)
            await save_screenshot(page, "04_senha_preenchida")

            print("➡️ Clicando em Entrar novamente...")
            entrar_buttons = page.locator("button:has-text('Entrar')")
            await entrar_buttons.last.click()

            # Verifica se apareceu erro de senha
            await page.wait_for_timeout(3000)
            if (
                await page.locator("text=Senha inválida").count() > 0
                or await page.locator("text=Senha incorreta").count() > 0
            ):
                print("❌ ERRO CRÍTICO: Senha inválida ou incorreta no Cisslive!")
                print("Atualize o Secret CISSLIVE_PASSWORD no GitHub.")
                await save_screenshot(page, "erro_senha_invalida")
                await browser.close()
                sys.exit(1)

            print("⏳ Aguardando login concluir e carregar a tela inicial...")
            try:
                await page.wait_for_selector("text=Relatório", timeout=90000)
            except Exception as wait_err:
                print(f"❌ Tempo limite de 90s esgotado ao aguardar o botão 'Relatório': {wait_err}")
                await save_screenshot(page, "erro_login_timeout")
                raise RuntimeError("Falha no login do Cisslive: a tela inicial não carregou a tempo.")
            await page.wait_for_timeout(1000)
            await save_screenshot(page, "05_tela_logado")

            # 4. Navigate to Reports
            print("📂 Procurando menu/botão de Relatório...")
            relatorio_button = page.locator("text=Relatório").first
            if await relatorio_button.count() == 0:
                relatorio_button = page.locator("span:has-text('Relatório')").first

            if await relatorio_button.count() > 0:
                print("🖱️ Clicando no menu Relatório...")
                await relatorio_button.click()
            else:
                print("⚠️ Botão 'Relatório' não encontrado por texto. Tentando navegar por atalhos...")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
                for _ in range(15):
                    await page.keyboard.press("Tab")
                await page.keyboard.press("ArrowRight")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
                await page.keyboard.type("relatório")
                await page.keyboard.press("Tab")
                await page.keyboard.press("Enter")

            print("⏳ Aguardando a tela de relatórios carregar...")
            try:
                await page.locator("text=Carregando...").wait_for(state="hidden", timeout=30000)
            except Exception:
                pass

            try:
                await page.wait_for_selector("text=Controle de Lote", timeout=30000)
            except Exception:
                try:
                    await page.wait_for_selector("text=5358", timeout=15000)
                except Exception:
                    pass

            await page.wait_for_timeout(2000)
            await save_screenshot(page, "06_menu_relatorio_aberto")

            # 5. Select Report 5358
            print("🔍 Buscando e abrindo relatório 5358 / Controle de Lote...")
            report_item = page.locator("text=5358").first
            if await report_item.count() == 0:
                report_item = page.locator("text=Controle de Lote").first

            if await report_item.count() == 0:
                print("⌨️ Digitando '5358' para filtrar a lista...")
                try:
                    await page.fill('input[placeholder="Pesquisar"]', "5358", timeout=5000)
                    await page.press('input[placeholder="Pesquisar"]', "Enter")
                except Exception:
                    await page.keyboard.type("5358")
                    await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)
                report_item = page.locator("text=5358").first
                if await report_item.count() == 0:
                    report_item = page.locator("text=Controle de Lote").first

            await save_screenshot(page, "07_resultado_busca_5358")

            if await report_item.count() > 0:
                print("🖱️ Dando duplo clique no relatório 5358/Controle de Lote...")
                await report_item.dblclick()
            else:
                print("⚠️ Item '5358' ou 'Controle de Lote' não encontrado por texto. Simulando Enter...")
                await page.keyboard.press("Enter")

            await page.wait_for_timeout(5000)
            await save_screenshot(page, "08_parametros_relatorio_aberto")

            # 6. Report Parameters (Tipo de Custo = 4, Dates = start_date to end_date)
            print("🔍 Buscando campo 'Tipo de Custo'...")
            tipo_custo_input = page.locator("input[name='RA_TIPOCUSTO']").first
            if await tipo_custo_input.count() > 0:
                input_id = await tipo_custo_input.get_attribute("id")
                base_id = input_id.replace("-inputEl", "")
                trigger_id = f"#{base_id}-trigger-open"

                print("🖱️ Clicando na lupa de Tipo de Custo...")
                await page.click(trigger_id)
                await page.wait_for_timeout(2000)
                await save_screenshot(page, "09_tipo_custo_busca")

                # Select option 4 (Preço de Venda)
                print("🖱️ Buscando opção 'Preço de Venda'...")
                opcao_4 = page.locator("text=Preço de Venda").first
                if await opcao_4.count() == 0:
                    opcao_4 = page.locator("text=4").first

                if await opcao_4.count() > 0:
                    print("🖱️ Dando duplo clique na opção 'Preço de Venda'...")
                    await opcao_4.dblclick()
                else:
                    print("⚠️ Opção 'Preço de Venda' não encontrada visualmente. Tentando digitar '4'...")
                    await page.keyboard.type("4")
                    await page.keyboard.press("Enter")

                await page.wait_for_timeout(2000)
            else:
                print("⚠️ Campo 'Tipo de Custo' não encontrado!")

            # Dates configuration
            print("📅 Configurando datas...")
            initial_field = page.locator("input[name='RA_DT_INI']").first
            final_field = page.locator("input[name='RA_DT_FIM']").first

            if await initial_field.count() > 0:
                await initial_field.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.type(start_date)
                await page.keyboard.press("Tab")
                print(f"✅ Data inicial preenchida: {start_date}")
            else:
                print("⚠️ Campo de data inicial (RA_DT_INI) não encontrado.")

            if await final_field.count() > 0:
                await final_field.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.type(end_date)
                await page.keyboard.press("Tab")
                print(f"✅ Data final preenchida: {end_date}")
            else:
                print("⚠️ Campo de data final (RA_DT_FIM) não encontrado.")

            await save_screenshot(page, "10_datas_preenchidas")

            # 7. Generate Excel and Download
            print("📥 Iniciando download do Excel...")
            btn_xlsx_exists = await page.evaluate("""() => {
                return !!Ext.ComponentQuery.query('button[text="Gerar XLSX"]')[0];
            }""")

            async with page.expect_download(timeout=120000) as download_info:
                if btn_xlsx_exists:
                    print("🖱️ Botão 'Gerar XLSX' já está visível. Clicando diretamente...")
                    try:
                        await page.click('button:has-text("Gerar XLSX")', timeout=5000)
                    except Exception:
                        print("⚠️ Clicando no botão via script JS...")
                        await page.evaluate("""() => {
                            const btn = Ext.ComponentQuery.query('button[text="Gerar XLSX"]')[0];
                            if (btn) {
                                if (typeof btn.handler === 'function') {
                                    btn.handler(btn);
                                } else {
                                    btn.fireEvent('click', btn);
                                }
                            }
                        }""")
                else:
                    print("🖱️ Abrindo o menu do botão 'Gerar PDF'...")
                    await page.evaluate("""() => {
                        const btn = Ext.ComponentQuery.query('button[text="Gerar PDF"]')[0];
                        if (btn && btn.showMenu) {
                            btn.showMenu();
                        }
                    }""")
                    await page.wait_for_timeout(1500)
                    await save_screenshot(page, "11_menu_pdf_aberto")

                    print("🖱️ Clicando na opção 'Gerar XLSX'...")
                    try:
                        await page.click("text=Gerar XLSX", timeout=5000)
                    except Exception:
                        print("⚠️ Clicando no menuitem via script JS...")
                        await page.evaluate("""() => {
                            const item = Ext.ComponentQuery.query('menuitem[text="Gerar XLSX"]')[0];
                            if (item) {
                                if (typeof item.handler === 'function') {
                                    item.handler(item);
                                } else {
                                    item.fireEvent('click', item);
                                }
                            }
                        }""")

            download = await download_info.value
            print(f"💾 Download detectado: {download.suggested_filename}")

            TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
            await download.save_as(str(TARGET_PATH))
            print(f"✅ Arquivo salvo em: {TARGET_PATH}")

            await save_screenshot(page, "12_download_concluido")
            print("🎉 Processo de automação do browser concluído com sucesso!")

            # 8. Sincronizar com o Supabase
            print("🚀 Iniciando a importação do estoque para o Supabase...")
            try:
                # Set the file path for importar_estoque
                os.environ["PASTA_ARQUIVO"] = str(DOWNLOAD_DIR)
                os.environ["NOME_ARQUIVO"] = TARGET_FILE_NAME
                from importar_estoque import main as import_main

                import_main()
                print("✅ Sincronização com o Supabase concluída com sucesso!")
            except Exception as import_err:
                print("❌ Falha ao importar dados no Supabase:")
                traceback.print_exc()
                raise import_err

        except Exception as e:
            print("❌ Ocorreu um erro na automação do Cisslive:")
            traceback.print_exc()
            await save_screenshot(page, "erro_automacao")
            raise e
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_automation())
