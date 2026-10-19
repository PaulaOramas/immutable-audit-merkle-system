const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MerkleAnchor", function () {
  let contract;
  let owner;
  let other;

  const sampleRoot =
    "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890";
  const sampleRoot2 =
    "0x1111111111111111111111111111111111111111111111111111111111111111";
  const zeroBytesRoot =
    "0x0000000000000000000000000000000000000000000000000000000000000000";

  beforeEach(async function () {
    [owner, other] = await ethers.getSigners();
    const MerkleAnchor = await ethers.getContractFactory("MerkleAnchor");
    contract = await MerkleAnchor.deploy();
    await contract.waitForDeployment();
  });

  describe("Despliegue", function () {
    it("debería establecer el owner correctamente", async function () {
      expect(await contract.owner()).to.equal(owner.address);
    });

    it("debería iniciar con anchorCount = 0", async function () {
      expect(await contract.anchorCount()).to.equal(0);
    });
  });

  describe("anchorRoot", function () {
    it("debería anclar un Merkle Root exitosamente", async function () {
      const tx = await contract.anchorRoot(sampleRoot, "batch-001");
      await tx.wait();
      expect(await contract.anchorCount()).to.equal(1);
    });

    it("debería emitir el evento RootAnchored", async function () {
      await expect(contract.anchorRoot(sampleRoot, "batch-001"))
        .to.emit(contract, "RootAnchored");
    });

    it("debería almacenar los datos correctamente", async function () {
      await contract.anchorRoot(sampleRoot, "batch-001");
      const [root, timestamp, batchId] = await contract.getAnchor(0);
      expect(root).to.equal(sampleRoot);
      expect(timestamp).to.be.greaterThan(0);
      expect(batchId).to.equal("batch-001");
    });

    it("debería incrementar anchorCount por cada anclaje", async function () {
      await contract.anchorRoot(sampleRoot, "batch-001");
      await contract.anchorRoot(sampleRoot2, "batch-002");
      expect(await contract.anchorCount()).to.equal(2);
    });

    it("debería rechazar Merkle Root vacío", async function () {
      await expect(
        contract.anchorRoot(zeroBytesRoot, "batch-fail")
      ).to.be.revertedWith("Merkle root no puede ser vacio");
    });

    it("debería rechazar llamadas de no-owner", async function () {
      await expect(
        contract.connect(other).anchorRoot(sampleRoot, "batch-unauth")
      ).to.be.revertedWith("Solo el owner puede anclar");
    });

    it("debería permitir anclar el mismo root múltiples veces", async function () {
      await contract.anchorRoot(sampleRoot, "batch-001");
      await contract.anchorRoot(sampleRoot, "batch-001-dup");
      expect(await contract.anchorCount()).to.equal(2);
    });
  });

  describe("getAnchor", function () {
    it("debería retornar datos correctos", async function () {
      await contract.anchorRoot(sampleRoot, "batch-get-test");
      const [root, , batchId] = await contract.getAnchor(0);
      expect(root).to.equal(sampleRoot);
      expect(batchId).to.equal("batch-get-test");
    });

    it("debería rechazar ID inexistente", async function () {
      await expect(contract.getAnchor(0)).to.be.revertedWith("Anclaje no existe");
    });

    it("debería rechazar ID fuera de rango", async function () {
      await contract.anchorRoot(sampleRoot, "batch-001");
      await expect(contract.getAnchor(5)).to.be.revertedWith("Anclaje no existe");
    });
  });

  describe("verifyRoot", function () {
    it("debería encontrar un root anclado", async function () {
      await contract.anchorRoot(sampleRoot, "batch-verify");
      const [found, anchorId, timestamp] = await contract.verifyRoot(sampleRoot);
      expect(found).to.be.true;
      expect(anchorId).to.equal(0);
      expect(timestamp).to.be.greaterThan(0);
    });

    it("debería retornar false para root no anclado", async function () {
      await contract.anchorRoot(sampleRoot, "batch-001");
      const [found] = await contract.verifyRoot(sampleRoot2);
      expect(found).to.be.false;
    });

    it("debería encontrar el primero con duplicados", async function () {
      await contract.anchorRoot(sampleRoot, "batch-first");
      await contract.anchorRoot(sampleRoot, "batch-second");
      const [found, anchorId] = await contract.verifyRoot(sampleRoot);
      expect(found).to.be.true;
      expect(anchorId).to.equal(0);
    });

    it("debería funcionar con múltiples roots", async function () {
      await contract.anchorRoot(sampleRoot, "batch-a");
      await contract.anchorRoot(sampleRoot2, "batch-b");

      const [f1, id1] = await contract.verifyRoot(sampleRoot);
      expect(f1).to.be.true;
      expect(id1).to.equal(0);

      const [f2, id2] = await contract.verifyRoot(sampleRoot2);
      expect(f2).to.be.true;
      expect(id2).to.equal(1);
    });
  });

  describe("Flujo de integración", function () {
    it("debería simular el flujo completo", async function () {
      const batches = [
        { root: sampleRoot, id: "batch-001" },
        { root: sampleRoot2, id: "batch-002" },
        { root: "0x9999999999999999999999999999999999999999999999999999999999999999", id: "batch-003" },
      ];

      for (const batch of batches) {
        await contract.anchorRoot(batch.root, batch.id);
      }

      expect(await contract.anchorCount()).to.equal(3);

      for (let i = 0; i < batches.length; i++) {
        const [root, timestamp, batchId] = await contract.getAnchor(i);
        expect(root).to.equal(batches[i].root);
        expect(batchId).to.equal(batches[i].id);
        expect(timestamp).to.be.greaterThan(0);
      }

      for (const batch of batches) {
        const [found] = await contract.verifyRoot(batch.root);
        expect(found).to.be.true;
      }
    });
  });
});
