# PSC record field guide

## Record selection

Extract one champion single-junction device. Rank devices by explicitly reported scan PCE, not stabilized output, certification, module efficiency, tandem efficiency, or a value quoted from prior work. If forward and reverse scans differ, use the larger reported scan only to identify the device, then retain both directions in their respective fields.

Map sample codes across the main text and supplement before combining fabrication and performance values. Treat a stability specimen as a different device unless the authors explicitly identify it as the champion.

## General encoding

- Emit all values as strings and use `Null` for unavailable information.
- Preserve useful units. Normalize only unambiguous typography such as `cm^2` versus `cm2`.
- Use `/` to align properties of successive layers and `;` to separate precursor solutions, additives, or steps within one field.
- Do not infer ambient pressure, room temperature, nitrogen purity, relative humidity, film thickness, or device area when absent.

## Reference and cell definition

`Ref_DOI` may be `Null` for a synthetic or unpublished document. `Cell_architecture` is `PIN` when the hole-selective contact is below the absorber and `NIP` when the electron-selective contact is below it. Report the complete electrically active stack from transparent electrode to rear electrode. `Cell_area_measured` is the illuminated mask/aperture area used for the reported J--V result, not substrate size.

## Transport layers and contacts

Assign self-assembled monolayers and hole-selective polymers to the HTL side; assign fullerene, metal-oxide, and buffer layers on the electron-collecting side to the ETL side. A post-treatment on the absorber belongs to the surface-treatment fields even if it improves the adjoining transport contact. Report vacuum pressure only when stated.

## Perovskite absorber

Preserve nominal stoichiometry, including mixed A-site cations and halides. Distinguish one-step antisolvent deposition from two-step sequential conversion. In one-step processing, list the mixed precursor as one reaction solution; in sequential processing, preserve each solution and concentration in order. `Perovskite_additive_*` refers only to material mixed into a precursor before coating.

For spin programs, preserve ordered stages such as `1000/5000 rpm` and `10/30 s`. Record the antisolvent and its application only when explicitly reported. A bandgap derived solely from composition is `Null`; a reported optical or photovoltaic bandgap may be used.

## J--V and stabilized output

Use the same champion device across the reverse and forward scan fields. Record `Voc` in V, `Jsc` in mA cm-2, FF in percent, and PCE in percent. Do not place an EQE-integrated current in a J--V field. Certification requires an external accredited laboratory or an explicitly identified certified report. Stabilized output requires maximum-power-point tracking or a stated stabilized power measurement, not a single delayed scan.

## Stability

Record the stress temperature, atmosphere, spectrum, intensity, humidity, duration, and final performance from one representative test. Prefer an operational maximum-power-point test of the champion architecture. Preserve whether the final value is absolute PCE (`24.1%`) or retention (`92% of initial`). Do not silently convert between them.
