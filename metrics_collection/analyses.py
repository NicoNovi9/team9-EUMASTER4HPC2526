#anova 0.5 alpha + boxplots for mistral64 and mistral128
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Load the two CSV files
mistral64 = pd.read_csv('tps_csvs/mistral64.csv')
mistral128 = pd.read_csv('tps_csvs/mistral128.csv')

# Add a grouping column to each dataframe
mistral64['memory'] = '64GB'
mistral128['memory'] = '128GB'

# Combine into single dataframe for analysis
df = pd.concat([mistral64, mistral128], ignore_index=True)

print("="*60)
print("ANOVA ANALYSIS: Mistral 64GB vs 128GB")
print("="*60)

# Descriptive Statistics
print("\nDESCRIPTIVE STATISTICS:")
print("-"*60)
summary = df.groupby('memory')['tps'].agg(['count', 'mean', 'std', 'min', 'max', 'median'])
print(summary)

# One-way ANOVA
print("\n" + "="*60)
print("ONE-WAY ANOVA (α = 0.05)")
print("="*60)

group_64 = mistral64['tps'].values
group_128 = mistral128['tps'].values

f_stat, p_value = stats.f_oneway(group_64, group_128)

print(f"\nNull Hypothesis (H0): No difference in mean TPS between 64GB and 128GB")
print(f"Alternative Hypothesis (H1): Significant difference in mean TPS")
print(f"\nF-statistic: {f_stat:.4f}")
print(f"P-value: {p_value:.6f}")
print(f"\nSignificance level (α): 0.05")

if p_value < 0.05:
    print(f"Result: REJECT H0 (p = {p_value:.6f} < 0.05)")
    print("Conclusion: Significant difference in TPS between 64GB and 128GB")
else:
    print(f"Result: FAIL TO REJECT H0 (p = {p_value:.6f} >= 0.05)")
    print("Conclusion: No significant difference in TPS between 64GB and 128GB")

# Effect size (Cohen's d)
mean_64 = group_64.mean()
mean_128 = group_128.mean()
pooled_std = np.sqrt(((len(group_64)-1)*group_64.std()**2 + (len(group_128)-1)*group_128.std()**2) / (len(group_64)+len(group_128)-2))
cohens_d = (mean_128 - mean_64) / pooled_std

print(f"\nEffect size (Cohen's d): {cohens_d:.4f}")
print(f"Interpretation: ", end="")
if abs(cohens_d) < 0.2:
    print("Negligible effect")
elif abs(cohens_d) < 0.5:
    print("Small effect")
elif abs(cohens_d) < 0.8:
    print("Medium effect")
else:
    print("Large effect")

# Create boxplot
print("\n" + "="*60)
print("GENERATING BOXPLOT...")
print("="*60)

fig, ax = plt.subplots(figsize=(10, 6))

# Create boxplot
bp = ax.boxplot([group_64, group_128], 
                 labels=['64GB', '128GB'],
                 patch_artist=True,
                 widths=0.6)

# Customize colors
colors = ['#ff9999', '#66b3ff']
for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

# Styling
ax.set_xlabel('Memory Allocation', fontsize=12, fontweight='bold')
ax.set_ylabel('Tokens Per Second (TPS)', fontsize=12, fontweight='bold')
ax.set_title(f'Mistral TPS Comparison: 64GB vs 128GB\n(p-value = {p_value:.6f} 100 parallel clients)', 
             fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3, linestyle='--')

# Add mean markers
means = [mean_64, mean_128]
ax.plot([1, 2], means, 'D', color='red', markersize=8, label='Mean', zorder=3)

# Add sample size annotations
ax.text(1, ax.get_ylim()[0] + 0.02*(ax.get_ylim()[1]-ax.get_ylim()[0]), 
        f'n={len(group_64)}', ha='center', fontsize=10)
ax.text(2, ax.get_ylim()[0] + 0.02*(ax.get_ylim()[1]-ax.get_ylim()[0]), 
        f'n={len(group_128)}', ha='center', fontsize=10)

# Add significance annotation
y_max = max(group_64.max(), group_128.max())
y_range = ax.get_ylim()[1] - ax.get_ylim()[0]

if p_value < 0.05:
    # Draw significance bar
    ax.plot([1, 1, 2, 2], [y_max + 0.05*y_range, y_max + 0.08*y_range, 
                            y_max + 0.08*y_range, y_max + 0.05*y_range], 
            'k-', linewidth=1.5)
    ax.text(1.5, y_max + 0.09*y_range, '*', ha='center', fontsize=20)
    ax.text(1.5, y_max + 0.12*y_range, f'p = {p_value:.4f}', ha='center', fontsize=10)
else:
    ax.text(1.5, y_max + 0.08*y_range, 'n.s.', ha='center', fontsize=4, style='italic')

ax.legend()

plt.tight_layout()
plt.savefig('mistral_64gb_vs_128gb_boxplot.png', dpi=300, bbox_inches='tight')
print("✓ Boxplot saved as: mistral_64gb_vs_128gb_boxplot.png")

plt.show()

print("\n" + "="*60)
print("ANALYSIS COMPLETE")
print("="*60)
###### anova and saturation analysis(ie tps decay over parallel clients) for mistral 64gb
import matplotlib.pyplot as plt
import pandas as pd

# Data from your table
data = {
    "clients": [1, 2, 4, 8, 16],
    "heavy_seq": [129.85, 70.31, 48.69, 32.89, 17.57],   # 100 sequential requests
    "light_seq": [114.23, 63.50, 57.85, 33.85, 16.90],  # 10 sequential requests
    "fixed_total": [124.11, 73.65, 37.63, 20.01, 8.15], # clients * seq_reqs = 16
}

df = pd.DataFrame(data)

fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(df["clients"], df["heavy_seq"],  marker="o", linewidth=2,
        label="Heavy seq. (100 req/client)")
ax.plot(df["clients"], df["light_seq"],  marker="s", linewidth=2,
        label="Light seq. (10 req/client)")
ax.plot(df["clients"], df["fixed_total"], marker="^", linewidth=2,
        label="Fixed total (clients×reqs=16)")

ax.set_xscale("log", base=2)  # 1,2,4,8,16 leggibili
ax.set_xticks(df["clients"])
ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

ax.set_xlabel("Number of parallel clients", fontsize=11)
ax.set_ylabel("Average TPS", fontsize=11)
ax.set_title("Mistral – TPS vs parallel clients (RAM=64GB, GPU partition)", fontsize=12)
ax.legend()
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("mistral_saturation_lines.png", dpi=300)
plt.show()
