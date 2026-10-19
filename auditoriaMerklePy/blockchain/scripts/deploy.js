const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("🚀 Desplegando MerkleAnchor...\n");

  const network = hre.network.name;
  const [deployer] = await hre.ethers.getSigners();
  const balance = await hre.ethers.provider.getBalance(deployer.address);

  console.log(`  Red:       ${network}`);
  console.log(`  Deployer:  ${deployer.address}`);
  console.log(`  Balance:   ${hre.ethers.formatEther(balance)} ETH\n`);

  const outputPath = path.join(__dirname, "..", "deployed_address.json");
  if (fs.existsSync(outputPath)) {
    try {
      const deployInfo = JSON.parse(fs.readFileSync(outputPath, "utf8"));
      const code = await hre.ethers.provider.getCode(deployInfo.contractAddress);
      if (code !== "0x") {
        console.log(`✅ Contrato previamente desplegado detectado en: ${deployInfo.contractAddress}`);
        console.log(`   (La blockchain mantuvo su estado, omitiendo redespliegue)`);
        return;
      } else {
        console.log(`⚠️ Contrato no encontrado en la blockchain (reinicio detectado). Redesplegando...`);
      }
    } catch (e) {
      console.log(`⚠️ Error leyendo estado anterior. Redesplegando...`);
    }
  }

  const MerkleAnchor = await hre.ethers.getContractFactory("MerkleAnchor");
  const contract = await MerkleAnchor.deploy();
  await contract.waitForDeployment();

  const contractAddress = await contract.getAddress();
  console.log(`✅ MerkleAnchor desplegado en: ${contractAddress}`);
  console.log(`   Owner: ${await contract.owner()}`);
  console.log(`   AnchorCount: ${await contract.anchorCount()}`);

  const deployInfo = {
    network: network,
    contractAddress: contractAddress,
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
    abi: "artifacts/contracts/MerkleAnchor.sol/MerkleAnchor.json",
  };

  // outputPath ya fue declarado arriba
  fs.writeFileSync(outputPath, JSON.stringify(deployInfo, null, 2));
  console.log(`\n📄 Info guardada en: ${outputPath}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Error:", error);
    process.exit(1);
  });
