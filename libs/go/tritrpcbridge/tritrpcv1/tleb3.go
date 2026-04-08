package tritrpcv1

import "errors"

func TLEB3EncodeLen(n uint64) []byte {
	var digits []byte
	if n == 0 {
		digits = []byte{0}
	} else {
		for n > 0 {
			digits = append(digits, byte(n%9))
			n /= 9
		}
	}
	var trits []byte
	for i, d := range digits {
		c := byte(0)
		if i < len(digits)-1 {
			c = 2
		}
		p1 := d / 3
		p0 := d % 3
		trits = append(trits, c, p1, p0)
	}
	return TritPack243(trits)
}

func TLEB3DecodeLen(buf []byte, offset int) (val uint64, newOff int, err error) {
	trits := []byte{}
	off := offset
	processedDigits := 0
	for {
		group, next, err := unpackPackedTritGroup(buf, off)
		if err != nil {
			return 0, 0, err
		}
		off = next
		trits = append(trits, group...)
		for processedDigits < len(trits)/3 {
			j := processedDigits
			c, p1, p0 := trits[3*j], trits[3*j+1], trits[3*j+2]
			digit := uint64(p1)*3 + uint64(p0)
			mul := uint64(1)
			for k := 0; k < j; k++ {
				mul *= 9
			}
			val += digit * mul
			processedDigits++
			if c == 0 {
				return val, off, nil
			}
		}
	}
}

func unpackPackedTritGroup(buf []byte, off int) ([]byte, int, error) {
	if off >= len(buf) {
		return nil, 0, errors.New("EOF in TLEB3")
	}
	b := buf[off]
	off++
	if b <= 242 {
		val := int(b)
		group := make([]byte, 5)
		for j := 4; j >= 0; j-- {
			group[j] = byte(val % 3)
			val /= 3
		}
		return group, off, nil
	}
	if b >= 243 && b <= 246 {
		if off >= len(buf) {
			return nil, 0, errors.New("truncated tail")
		}
		k := int(b - 243 + 1)
		val := int(buf[off])
		off++
		group := make([]byte, k)
		for j := k - 1; j >= 0; j-- {
			group[j] = byte(val % 3)
			val /= 3
		}
		return group, off, nil
	}
	return nil, 0, errors.New("invalid byte 247..255")
}
