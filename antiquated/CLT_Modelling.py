import numpy as np
import matplotlib.pyplot as plt

# Function to simulate CLT with a uniform distribution and varying sample sizes
def simulate_clt_uniform_distribution(num_samples_list, sample_size):
    plt.figure(figsize=(12, 8))

    for num_samples in num_samples_list:
        means = []
        for _ in range(num_samples):
            # Draw 'sample_size' number of values from a uniform distribution between 1 and 10
            sample = np.random.uniform(1, 100, sample_size)
            sample_mean = np.mean(sample)
            means.append(sample_mean)

        # Plot histogram of sample means
        plt.hist(means, bins=1000, alpha=0.5, label=f'n={sample_size}, Samples={num_samples}')

    plt.xlabel('Sample Mean')
    plt.ylabel('Frequency')
    plt.title('Central Limit Theorem Simulation with Uniform Distribution')
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.show()

# Sample sizes and the number of sums to try
num_samples_list = [100, 500, 1000, 5000, 50000]  # Number of sums to plot for each
sample_size = 100  # Size of each sample

# Run the simulation
simulate_clt_uniform_distribution(num_samples_list, sample_size)
