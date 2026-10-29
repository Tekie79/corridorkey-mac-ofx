# License and attribution

This is an independent experimental integration for **CorridorKey**, created for local development and evaluation. It is not an official Corridor Digital plugin and does not imply endorsement by Corridor Digital, Blackmagic Design, Apple, or the OpenFX project.

CorridorKey 2.0 model design: Zachary Harris, in collaboration with Niko Pueringer and Corridor Digital. Official source: https://github.com/nikopueringer/CorridorKey2.0 .

## Integration code

The original integration source in this archive is offered under the same Corridor Key Licence v2 terms reproduced in `licenses/CorridorKey-LICENSE.txt`, insofar as those terms apply to this contribution. No permission is granted here beyond the rights the relevant authors hold. All pre-existing third-party code and models retain their own licenses.

## Upstream is source-available with restrictions

The upstream license is a custom Corridor Key Licence based on CC BY-NC-SA 4.0 with overriding additional terms. It is not a permissive open-source software license. It allows processing commercial footage, and states that resulting images and videos belong to their creator. It also contains restrictions on repackaging, redistribution, competing products, paid inference services, and commercial software integration.

The license requires released derivatives incorporating the tool to remain freely available, retain prominent CorridorKey attribution, and use the same or substantially equivalent terms. It also has a separate licensing condition for entities above its stated annual revenue threshold. Read the complete upstream terms rather than treating this summary as clearance for a product release.

The broad restriction on repackaging/redistributing a standalone or competing product and the permission for free derivatives require care. A source-only adapter and separate model downloads do not automatically settle all distribution questions. Obtain clarification from the licensor before distributing a competing bundled plugin or incorporating this into commercial software such as a paid application or service.

The archive intentionally contains no upstream model weights, no full CorridorKey source checkout, and no official plugin binaries. Setup retrieves publisher assets separately. The third-party model notices are included for reference in `licenses/CorridorKey-THIRD_PARTY_NOTICES.md`.

## OpenFX

OpenFX headers are downloaded separately from the Academy Software Foundation repository. Their license is reproduced in `licenses/OpenFX-LICENSE.txt`. Attribution and license retention are required for any distributed SDK material according to that license.

## No certification

The source is provided as an experimental development artifact, without a claim of production readiness, Mac GPU operator coverage, image-quality equivalence, real-time performance, or native host certification. Consult `docs/VALIDATION.md` for the actual tests performed.
