import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        String a2 = Verifier.nondetString();
        testConc(a1);
        testSym(a1, a2);
    }

    public static void testConc(String s1) {
        StringBuilder sb = new StringBuilder(s1);
        String s2 = sb.reverse().toString();
        if (s2.equals("desserts")) {
            System.out.println("s1 reversed equals desserts");
        }
    }

    public static void testSym(String s1, String s2) {
        StringBuilder sb = new StringBuilder(s1);
        String s3 = sb.reverse().toString();
        if (s3.equals(s2)) {
            System.out.println("s1 reversed equals s2");
        }
    }
}
