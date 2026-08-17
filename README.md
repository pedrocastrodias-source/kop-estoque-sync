# Kopenhagen - Sincronização Automática de Estoque

Automação que baixa o relatório 5358 (Controle de Lote) do Cisslive e sincroniza os dados de estoque com o Supabase.

## ⚡ Como Funciona

1. **GitHub Actions** executa automaticamente a cada hora (8h-20h, seg-sáb)
2. O script abre o Cisslive via navegador headless (Playwright)
3. Faz login, gera o relatório Excel e baixa o arquivo
4. Filtra produtos descontinuados e envia os dados para o Supabase

## 🔐 Secrets Necessários

Configure os seguintes Secrets no repositório (`Settings → Secrets and variables → Actions`):

| Secret | Descrição |
|--------|-----------|
| `CISSLIVE_USERNAME` | E-mail de login do Cisslive |
| `CISSLIVE_PASSWORD` | Senha do Cisslive |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_KEY` | Chave de API do Supabase |

## 🚀 Execução Manual

Para rodar manualmente: vá em **Actions → Sincronizar Estoque → Run workflow**

## 📋 Produtos Descontinuados (filtrados automaticamente)

- `2002299` - MINITABLETE BRANCO FRIENDS 10G
- `2002298` - MINITABLETE AO LEITE FRIENDS 10G
