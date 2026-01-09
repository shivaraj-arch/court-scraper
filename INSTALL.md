# 🛠️ Installation Guide - Karnataka High Court Tracker

Follow these steps to deploy the automated tracking and analytics system.

---

## 🏗️ 1. Database Design (Supabase)

Instead of manual table creation, the system uses a **Normalized Relational Schema** optimized for alphanumeric court data.

### Core Schema Architecture:
| Entity | Storage Type | Primary Key / Unique Constraints |
| :--- | :--- | :--- |
| **Cause List** | `TEXT` Based | `case_number` (Unique) |
| **Heard Cases** | `TEXT` Based | `date`, `court_hall`, `case_number` |
| **Judge Stats** | `NUMERIC` Metrics | `date`, `court_hall`, `judge_name` |
| **Case History** | `JSONB` Metadata | `case_number` (Unique) |

**Deployment Step:**
1. Create a new project in [Supabase](https://supabase.com).
2. Open the **SQL Editor**.
3. Run the `schema_v2_alphanumeric.sql` script (provided in the `/database` folder of this repo). 
   *Note: This schema is "Alphanumeric Safe," supporting halls like '2A' and serials like '44.1'.*

---

## 🚀 2. GitHub Actions Deployment (Cloud)

Perfect for a "Set it and Forget it" deployment.

1. **Fork this Repository** to your own GitHub account.
2. **Configure Secrets**: Navigate to `Settings` -> `Secrets and Variables` -> `Actions`.
3. Add the following:
   - `SUPABASE_URL`: Your project URL.
   - `SUPABASE_KEY`: Your service/anon key.
4. **Enable Workflows**: Go to the `Actions` tab and click **"Enable Workflows"**.

---

## 💻 3. Local macOS/Linux Deployment

For users requiring 15-second "Ultra-Live" updates (bypassing GitHub's 5-minute limit).

### Step 1: Environment Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt