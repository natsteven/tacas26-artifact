import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        String a2 = Verifier.nondetString();
        testSym(a1, a2);
        testConc(a2);
    }

    public static void testConc(String s1) {
        if (s1.indexOf("Hello") == 0) {
            System.out.println("s1 starts with 'Hello'");
        } else if (s1.indexOf("World") == 2){
			System.out.println("s1 starts with 'World' at index 2");
		}
    }

    public static void testSym(String s1, String s2) {
		String s3 = s1.concat(s2);
        if (s3.indexOf(s2) > 0) {
            System.out.println("s1 starts with s2");
        }
		if (s3.indexOf(s1) == 0) {
			System.out.println("s1 and s2 are the same");
		}
    }
}
