import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        testFirst(a1);
        testAll(a1);
		testFirstAllSym(a1);
    }

    public static void testFirst(String s1) {
        String s2 = s1.replaceFirst("a", "b");
        if (s2.equals("ba")) {
            System.out.println("s2 equals \"ba\"");
        } else {
            System.out.println("s2 does not equal \"aa\"");
        }
		assert(s2.equals("aa"));
    }

    public static void testAll(String s1) {
        String s2 = s1.replace("a", "b");
        if (s2.equals("aa")) {
            System.out.println("s2 equals \"muggy\"");
        } else {
            System.out.println("s2 does not equal \"muggy\"");
        }
    }

	public static void testFirstAllSym(String s1){
		String s2 = Verifier.nondetString();
		String s3 = Verifier.nondetString();
		String s4 = s1.replaceFirst(s2, s3);
		if (s4.equals("aa")){
			System.out.println("s4 equals \"aa\"");
		} else {
			System.out.println("s4 does not equal \"aa\"");
		}
	}
}
