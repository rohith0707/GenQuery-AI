# SQL Generation LLM - Generative SQL Intelligence

A production-ready Streamlit application that translates natural language questions into optimized Snowflake SQL queries using OpenAI's language models.

## 🌟 Features

### Core Capabilities
- **Natural Language to SQL**: Ask analytical questions in plain English, get Snowflake-optimized SQL
- **Query Optimization**: AI-powered optimization to reduce query complexity and execution time
- **Safe Read-Only Execution**: Automatic validation ensures only SELECT/WITH queries are executed
- **Intelligent Schema Introspection**: Automatic database schema discovery for better query accuracy
- **Interactive Data Visualization**: Built-in charts (Bar, Line, Area, Time Series, Heatmaps)
- **Query History**: Track and review recent queries with execution statistics
- **Error Recovery**: Smart table name suggestion and automatic query regeneration on failures

### Security Features
- DDL/DML operation blocking (CREATE, DROP, INSERT, UPDATE, DELETE, ALTER)
- SQL injection prevention through sanitization
- Read-only Snowflake role enforcement
- Environment variable protection

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Snowflake account with read-only access
- OpenAI API key
- Git

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd SQL_Generation_LLM
```

2. **Create virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env` file in the project root:
```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here

# Snowflake Configuration
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=orgname-account.region
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema
SNOWFLAKE_ROLE=READ_ONLY_ROLE

# Query Limits
MAX_QUERY_ROWS=5000
```

5. **Run the application**
```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

## 🎥 Project Demo
Click below to watch the video demo 👇  
[![AI SQL Generation Agent Demo](https://img.shields.io/badge/Watch%20Demo-Click%20Here-blue?style=for-the-badge)](https://github.com/rohith0707/GenQuery-AI/blob/main/AI%20SQL%20Generation%20Agent.mp4)



## 📖 Usage Guide

### Main SQL Generation Interface

1. **Enter your question** in natural language:
   - "Total revenue by region for Q2 2024"
   - "Top 10 customers by lifetime value"
   - "Monthly order count trend last 12 months"

2. **Add schema context** (optional but recommended):
   ```
   orders(id, customer_id, amount, created_at)
   customers(id, region, channel, lifetime_value)
   ```

3. **Click "🚀 Generate & Run"**

4. **Review results** in three tabs:
   - **SQL**: Generated query with copy button
   - **Data**: Results table with CSV download
   - **Visualization**: Interactive charts

### Query Optimization Feature

Access via the **🛠 Query Optimization** button in the sidebar.

**Purpose**: Optimize existing complex Snowflake queries to reduce execution time and improve performance.

**How to use**:
1. Click the Query Optimization button in the sidebar
2. Paste your complex SQL query into the text area
3. Click "⚙️ Optimize"
4. Review the side-by-side comparison
5. Check structural metrics (lines, JOINs, CTEs, etc.)
6. Copy the optimized query for use

**Optimization Techniques**:
- Removes unused CTEs
- Pushes WHERE filters earlier
- Removes redundant DISTINCT/ORDER BY
- Converts subqueries to QUALIFY for window functions
- Applies Snowflake-specific best practices

For detailed information, see [`QUERY_OPTIMIZATION_GUIDE.md`](QUERY_OPTIMIZATION_GUIDE.md).

## 🏗️ Architecture

### Project Structure
```
SQL_Generation_LLM/
├── app.py                          # Main Streamlit application
├── langchain_agent.py              # SQL generation & optimization logic
├── snowflake_client.py             # Snowflake connection & execution
├── sql_validator.py                # Safety validation & sanitization
├── utils.py                        # Utilities & logging
├── ui_styles.py                    # CSS styling
├── design_tokens.py                # Design system tokens
├── pages/
│   └── Query_Optimization.py       # Query optimization page
├── ui/
│   └── components.py               # Reusable UI components
├── requirements.txt                # Python dependencies
├── .env                            # Environment configuration (not committed)
└── README.md                       # This file
```

### Technology Stack
- **Frontend**: Streamlit, Altair (visualizations)
- **Backend**: Python 3.8+
- **Database**: Snowflake
- **AI/ML**: OpenAI API (GPT-4o-mini, GPT-3.5-turbo)
- **Libraries**: 
  - LangChain (SQL generation with schema introspection)
  - pandas (data manipulation)
  - sqlparse (SQL parsing)
  - tenacity (retry logic)

### Key Components

#### 1. SQL Generation ([`langchain_agent.py`](langchain_agent.py))
- **Primary Method**: OpenAI Responses API with GPT-4o-mini
- **Fallback**: Chat Completions API with GPT-3.5-turbo
- **Legacy Support**: text-davinci-003 for older OpenAI SDK versions
- **LangChain Integration**: Optional schema-aware generation using SQLDatabase

#### 2. Query Optimization ([`langchain_agent.py`](langchain_agent.py:282-406))
- LLM-based semantic rewriting
- Heuristic optimizations for common patterns
- Safety validation of optimized output
- Fallback to original query if optimization fails

#### 3. Snowflake Client ([`snowflake_client.py`](snowflake_client.py))
- Connection pooling with keep-alive
- Enhanced error messages with table suggestions
- Schema introspection for up to 40 tables
- Automatic retry logic with exponential backoff

#### 4. Safety Validation ([`sql_validator.py`](sql_validator.py))
- Comment removal
- Multi-statement blocking
- DDL/DML keyword detection
- SELECT/WITH whitelist enforcement

#### 5. UI Components ([`ui/components.py`](ui/components.py))
- Dark/Light mode support
- Responsive design
- Interactive charts (8+ types)
- Copy-to-clipboard functionality
- Query history tracking

## 🎨 UI Features

### Design System
- Modern gradient backgrounds (customizable for dark/light modes)
- Consistent color palette with accent colors
- Focus states and elevation tokens
- Smooth animations and transitions

### Visualization Options
1. **Bar Chart**: Categorical vs. Numeric comparisons
2. **Line Chart**: Trends over categories
3. **Area Chart**: Cumulative trends
4. **Time Series**: Temporal data analysis
5. **Correlation Heatmap**: Multi-variable relationships
6. **Custom Builder**: Flexible chart configuration

### Dark Mode
Toggle in the sidebar for comfortable viewing in different lighting conditions.

## 🔒 Security Best Practices

1. **Read-Only Role**: Use a Snowflake role with only SELECT permissions
2. **Environment Variables**: Never commit `.env` file to version control
3. **API Key Rotation**: Regularly rotate OpenAI API keys
4. **Query Limits**: Configure `MAX_QUERY_ROWS` to prevent resource exhaustion
5. **Network Security**: Use Snowflake IP allowlists in production
6. **Audit Logging**: Monitor `genai_sql_agent.log` for suspicious activity

## 📊 Example Queries

### Revenue Analysis
```
Natural Language: "Show total revenue by region for Q2 2024"

Generated SQL:
SELECT 
    c.region,
    SUM(o.amount) as total_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.created_at BETWEEN '2024-04-01' AND '2024-06-30'
GROUP BY c.region
ORDER BY total_revenue DESC
```

### Customer Insights
```
Natural Language: "Top 10 customers by lifetime value"

Generated SQL:
SELECT 
    customer_id,
    lifetime_value
FROM customers
ORDER BY lifetime_value DESC
LIMIT 10
```

### Trend Analysis
```
Natural Language: "Monthly order count trend last 12 months"

Generated SQL:
SELECT 
    DATE_TRUNC('month', created_at) as month,
    COUNT(*) as order_count
FROM orders
WHERE created_at >= DATEADD(month, -12, CURRENT_DATE)
GROUP BY month
ORDER BY month
```

## 🔧 Configuration

### OpenAI Models
The application supports multiple OpenAI models with automatic fallback:
- **Primary**: `gpt-4o-mini` (Responses API) - Fast, cost-effective
- **Fallback**: `gpt-3.5-turbo` (Chat Completions) - Reliable
- **Legacy**: `text-davinci-003` (Completion) - Backward compatibility

### Snowflake Connection
Configure in `.env`:
- **Account**: Format `orgname-account.region` (e.g., `myorg-xy12345.us-east-1`)
- **Warehouse**: Computational resources (e.g., `COMPUTE_WH`)
- **Database/Schema**: Target data location
- **Role**: Use read-only role for safety

### Query Limits
- `MAX_QUERY_ROWS`: Maximum rows to fetch (default: 5000)
- Prevents memory issues with large result sets

## 🐛 Troubleshooting

### "OPENAI_API_KEY not set"
- Ensure `.env` file exists in project root
- Verify `OPENAI_API_KEY=sk-...` is correctly set
- Restart the application after updating `.env`

### "Snowflake account not reachable"
- Check `SNOWFLAKE_ACCOUNT` format (should include region)
- Verify network connectivity
- Confirm account is active and accessible

### "Object not found" errors
- Check `SNOWFLAKE_DATABASE` and `SNOWFLAKE_SCHEMA` settings
- Verify user has SELECT permission on target tables
- Review suggested table names in error message

### "Dangerous keyword detected"
- Query contains DDL/DML operations
- Use only SELECT or WITH statements
- Remove CREATE, DROP, INSERT, UPDATE, DELETE, ALTER

### Poor query quality
- Add schema context in sidebar
- Use more specific natural language
- Review and refine generated SQL manually
- Try rephrasing your question

## 📝 Development

### Running Tests
```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests (when available)
pytest tests/
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where applicable
- Add docstrings to functions
- Keep functions focused and modular

### Logging
Application logs are written to `genai_sql_agent.log`:
- INFO: General operational messages
- WARNING: Recoverable issues
- ERROR: Failed operations
- DEBUG: Detailed diagnostic information

### Adding New Features
1. Create feature branch
2. Update relevant modules
3. Add documentation
4. Test thoroughly
5. Update README.md

## 🚧 Known Limitations

1. **No Write Operations**: Only SELECT/WITH queries supported
2. **Schema Discovery Limits**: Maximum 40 tables, 40 columns per table
3. **No Query Cost Estimation**: Cannot predict Snowflake compute costs
4. **LLM Variability**: Results may vary between runs
5. **No Multi-Database Joins**: Limited to single database/schema context

## 🗺️ Roadmap

- [ ] Query execution plan visualization
- [ ] Saved query templates
- [ ] Multi-database support
- [ ] Query performance benchmarking
- [ ] User authentication and authorization
- [ ] Query scheduling and automation
- [ ] Advanced chart customization
- [ ] Export to various formats (Excel, JSON, Parquet)

## 📄 License

[Add your license information here]

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues, questions, or feature requests:
- Check existing documentation
- Review `genai_sql_agent.log` for errors
- Open an issue on GitHub
- Contact the development team

## 📚 Additional Documentation

- [`QUERY_OPTIMIZATION_GUIDE.md`](QUERY_OPTIMIZATION_GUIDE.md) - Detailed query optimization documentation
- [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) - UI/UX design guidelines (if available)

---

**Built for safe analytical exploration. Add governance, lineage & audit before productionization.**

**Version**: 1.0  
**Last Updated**: 2025-10-30
