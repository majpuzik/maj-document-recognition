# 🌐 Distributed Processing Guide

## 🚀 Overview

MAJ Document Recognition nyní podporuje **distribuované zpracování** napříč více Ollama servery v síti. To umožňuje **8× rychlejší** zpracování než single-server setup.

## 📊 Výkon

- **Single server**: ~45s/dokument
- **Distributed (2 servery, 8 workers)**: ~6s/dokument
- **Speedup**: 8× rychlejší! 🚀
- **Throughput**: ~10 dokumentů/minutu
- **2000 dokumentů**: ~3.3 hodiny

## 🏗️ Architektura

```
┌─────────────────┐
│   Mac Mini M4   │  ← Koordinátor (localhost)
│   CPU: 75%      │
│   MEM: 83%      │
└────────┬────────┘
         │
    Round-robin
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│Server1│ │Server2│
│Local  │ │.10.83 │
│4 work.│ │4 work.│
└───────┘ └───────┘
```

## 🔧 Požadavky

### Ollama servery v síti:
1. **localhost** - váš Mac
2. **192.168.10.83** (nebo jiné IP) - další server s Ollama

### Model requirements:
- Všechny servery musí mít **qwen2.5:32b** (nebo jiný velký model)
- Model musí být nahraný: `ollama pull qwen2.5:32b`

### Síťové požadavky:
- Port **11434/tcp** otevřený na všech serverech
- Nízká latence mezi servery (<10ms)

## 🚀 Quick Start

### 1. Najdi Ollama servery v síti

```bash
nmap -p 11434 192.168.10.0/24 --open -T4
```

### 2. Zkontroluj dostupné modely

```bash
curl -s http://192.168.10.83:11434/api/tags | python3 -c "import sys, json; print([m['name'] for m in json.load(sys.stdin)['models']])"
```

### 3. Spusť distributed processing

```bash
cd ~/maj-document-recognition
source venv/bin/activate
python distributed_parallel_test.py
```

### 4. Monitoruj progress

```bash
# Real-time monitoring
watch -n 60 '/tmp/monitor_distributed.sh'

# Nebo manuálně
/tmp/monitor_distributed.sh
```

## 📝 Konfigurace

Edit `distributed_parallel_test.py`:

```python
# Řádek ~42-46
OLLAMA_SERVERS = [
    "http://localhost:11434",
    "http://192.168.10.83:11434",
    "http://192.168.10.79:11434",  # Přidej další servery
]

# Řádek ~305 - workers per server
max_workers = num_servers * 4  # 4 workers per server
```

## 📊 Monitoring

### Real-time dashboard
```bash
/tmp/monitor_distributed.sh
```

**Output:**
```
=== DISTRIBUTED PROCESSING - 12:38:32 ===

📊 PROGRESS:
2025-11-06 12:38:27,107 - INFO - [568/2000] ✓ faktura (70%) [192.168.10.83]

Processed: 563/2000

📈 SYSTEM:
CPU: 59.2% | MEM: 83.3%

📡 SERVER DISTRIBUTION:
localhost:       282
192.168.10.83:  281

⏱️  Speed: ~10 docs/min | Remaining: 1437 | ETA: ~2.4h
```

### Log files
- **Main log**: `logs/distributed_run.log`
- **Completed docs**: `grep "✓" logs/distributed_run.log`
- **Errors**: `grep "ERROR\|WARN" logs/distributed_run.log`

### Database
```bash
sqlite3 ~/maj-document-recognition/data/documents.db "
  SELECT
    metadata->>'ollama_server' as server,
    document_type,
    COUNT(*) as count
  FROM documents
  WHERE metadata->>'ollama_server' IS NOT NULL
  GROUP BY server, document_type
  ORDER BY server, count DESC;
"
```

## 🔄 Load Balancing

System používá **round-robin** distribuci:
- doc_0 → localhost
- doc_1 → 192.168.10.83
- doc_2 → localhost
- doc_3 → 192.168.10.83
- ...

**Výsledek**: ~50/50 split mezi servery

## ⚙️ Resource Limits

System monitoruje **pouze LOCAL** resources:
- **CPU max**: 90%
- **Memory max**: 90%

Při překročení:
- ⚠️ Warning log
- 🛑 Cancel 2 pending tasks
- ⏸️ Wait 5s
- 🔄 Retry

**Remote servery** nejsou monitorovány (zatím).

## 🛠️ Troubleshooting

### Problém: Server nenalezen
```bash
# Test connectivity
curl -s http://192.168.10.83:11434/api/tags
```

**Fix**: Zkontroluj firewall, Ollama běží?

### Problém: Model chybí
```bash
# Na remote serveru
ssh admin@192.168.10.83
ollama pull qwen2.5:32b
```

### Problém: Timeout errors
**Symptom**: `ReadTimeoutError: Read timed out`

**Fix**:
1. Sniž workers per server: `max_workers = num_servers * 2`
2. NEBO použij menší model: `qwen2.5:7b`

### Problém: Unbalanced load
**Symptom**: localhost=400, remote=100

**Fix**: Round-robin by měl být 50/50. Check logs pro errors na jednom serveru.

## 📈 Performance Tuning

### Optimální workers per server:
- **M4 Mac**: 4 workers
- **M3 Mac**: 3 workers
- **M2 Mac**: 2 workers
- **Intel Mac**: 1-2 workers
- **Linux server**: 4-6 workers (dle CPU)

### Network latency:
- **<5ms**: Výborné
- **5-20ms**: Dobré
- **>20ms**: Sub-optimální (local processing je rychlejší)

## 🔮 Roadmap

### v1.1 (Plánováno):
- [ ] Automatic server discovery (mDNS/Avahi)
- [ ] Health checking remote servers
- [ ] Auto-recovery při server failure
- [ ] Progress persistence (resume po pádu)

### v1.2 (Možná):
- [ ] Web GUI pro distributed config
- [ ] REST API pro remote control
- [ ] Prometheus metrics
- [ ] Email notifikace po dokončení

## 📞 Support

**Issues**: https://github.com/majpuzik/maj-document-recognition/issues

**Logs**: `logs/distributed_run.log`

**Database**: `data/documents.db`

---

**Vytvořeno s ❤️ pomocí Claude Code**
