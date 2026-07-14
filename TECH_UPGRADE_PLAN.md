# NSE Pulse - Tech Stack Upgrade Plan

## 🔍 Identified Issues

### Critical Issues
1. **requirements.txt**
   - `nsepython>=0.1` - Broken/abandoned package causing import errors
   - `nselib>=0.1` - Outdated version (current is 0.3+)
   - Missing async HTTP client (httpx already listed but not used)
   - No retry/backoff library for resilient API calls

2. **Code Quality Issues**
   - `analysis_engine.py`: Incomplete type hints (missing `Dict`, `Optional`)
   - `app.py`: Uses `importlib.reload()` hack for Streamlit dev mode
   - Hardcoded dates in `news_provider.py` and `tickers.py` (will become stale)
   - No rate limiting or circuit breaker for NSE API calls
   - Synchronous blocking calls in async context (`analysis_engine.py`)

3. **Performance Issues**
   - No concurrent downloads in `data_provider.py` (already uses `threads=True` but could use async)
   - Supertrend calculation in pure Python loop (slow for large datasets)
   - No proper caching strategy for expensive computations

## 🚀 Tech Stack Upgrades

### Python Version
- **Current**: Python 3.10+
- **Upgrade to**: Python 3.12+ (3.13 recommended)
  - Better performance (2-8% faster)
  - Improved type hints (type parameter syntax)
  - Better error messages
  - New `typing` features

### Core Dependencies Upgrade

| Package | Current | Upgrade To | Reason |
|---------|---------|------------|--------|
| **streamlit** | >=1.30.0 | >=1.35.0 | Better performance, new features |
| **yfinance** | >=0.2.40 | >=0.2.38+ | Latest fixes for NSE data |
| **pandas** | >=2.0.0 | >=2.2.0 | Performance improvements, new API |
| **numpy** | >=1.24.0 | >=1.26.0 | Performance, better dtypes |
| **plotly** | >=5.18.0 | >=5.24.0 | Bug fixes, new chart types |
| **requests** | >=2.28.0 | >=2.32.0 | Security fixes |
| **nsepython** | >=0.1 | **REMOVE** | Broken package |
| **nselib** | >=0.1 | >=0.3.0 | Latest API |
| **fastapi** | >=0.100.0 | >=0.111.0 | Performance, new features |
| **uvicorn** | >=0.22.0 | >=0.30.0 | Better async support |
| **sse-starlette** | >=1.6.0 | >=2.0.0 | SSE improvements |
| **httpx** | >=0.24.0 | >=0.27.0 | Modern async HTTP |

### New Dependencies to Add

| Package | Version | Purpose |
|---------|---------|---------|
| **tenacity** | >=8.2.0 | Retry logic with exponential backoff |
| **aiofiles** | >=23.3.0 | Async file operations |
| **aiohttp** | >=3.9.0 | Async HTTP client for concurrent requests |
| **pydantic-settings** | >=2.0.0 | Configuration management |
| **python-dotenv** | >=1.0.0 | Environment variables |
| **rich** | >=13.7.0 | Terminal UI for CLI tools |
| **typer** | >=0.9.0 | CLI interface |
| **polars** | >=0.20.0 | Faster DataFrame operations (optional drop-in for pandas) |
| **cachetools** | >=5.3.0 | Advanced caching strategies |

## 🛠️ Code Modernization Tasks

### 1. Fix Dependencies (Priority: HIGH)
- [ ] Remove broken `nsepython` dependency
- [ ] Update `nselib` to >=0.3.0
- [ ] Add retry logic with `tenacity`
- [ ] Add async HTTP client `aiohttp`

### 2. Modernize Python Code (Priority: HIGH)
- [ ] Use `pathlib` instead of `os.path`
- [ ] Add complete type hints (mypy compliance)
- [ ] Replace `if/elif` chains with `match` statements (Python 3.10+)
- [ ] Use walrus operator (`:=`) where appropriate
- [ ] Add `@dataclass(frozen=True)` for immutable data structures

### 3. Performance Optimization (Priority: MEDIUM)
- [ ] Vectorize Supertrend calculation (remove Python loop)
- [ ] Use `polars` for large DataFrame operations
- [ ] Implement concurrent data downloads with `asyncio`
- [ ] Add proper caching with `cachetools`
- [ ] Use `numba` JIT compilation for indicator calculations (optional)

### 4. Architecture Improvements (Priority: MEDIUM)
- [ ] Implement circuit breaker pattern for API failures
- [ ] Add proper logging with `structlog`
- [ ] Add rate limiting for NSE API calls
- [ ] Separate concerns: extract data fetching from business logic
- [ ] Add configuration management (Pydantic Settings)

### 5. Testing & Quality (Priority: LOW)
- [ ] Add `pytest` for unit tests
- [ ] Add `pytest-asyncio` for async tests
- [ ] Add `mypy` for type checking
- [ ] Add `ruff` for linting
- [ ] Add `pre-commit` hooks

## 📋 Implementation Plan

### Phase 1: Critical Fixes
1. Fix broken dependencies
2. Update to latest stable versions
3. Add retry logic for API calls

### Phase 2: Code Modernization
1. Modernize Python syntax
2. Add complete type hints
3. Fix hardcoded values

### Phase 3: Performance
1. Vectorize calculations
2. Add concurrent operations
3. Optimize caching

### Phase 4: Polish
1. Add tests
2. Add proper logging
3. Documentation updates

## 🎯 Quick Wins (< 1 hour)
1. Update requirements.txt with latest versions
2. Remove `nsepython` dependency
3. Add `tenacity` for retries
4. Fix incomplete type hints in `analysis_engine.py`
5. Replace hardcoded dates with dynamic values